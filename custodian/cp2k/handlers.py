"""
Error handlers for CP2K calculations.

Handlers should be specific enough that they are not bulky (keep overhead low),
but if two handlers will always be called together, then consider joining them
into one handler.

When adding more remember the following tips:
(1) Handlers return True when the error is caught, and false if no error was caught
(2) CP2K error handlers will be different from VASP error handlers depending on if
    you are using Cp2k-specific functionality (like OT minimization).
(3) Not all things that could go wrong should be handled by custodian. For example,
    most aspects of walltime handling can be done natively in CP2K, and will have added
    benefits like writing a wavefunction restart file before quitting.
"""

import itertools
import os
import re
import time

import numpy as np
from monty.os.path import zpath
from monty.re import regrep
from monty.serialization import dumpfn
from pymatgen.io.cp2k.inputs import Cp2kInput, Keyword
from pymatgen.io.cp2k.outputs import Cp2kOutput

from custodian.cp2k.interpreter import Cp2kModder
from custodian.cp2k.utils import get_conv, restart, tail
from custodian.custodian import ErrorHandler

__author__ = "Nicholas Winner"
__version__ = "1.0"
__email__ = "nwinner@berkeley.edu"
__date__ = "March 2022"


CP2K_BACKUP_FILES = {"cp2k.out", "cp2k.inp", "std_err.txt"}
MINIMUM_BAND_GAP = 0.1


class StdErrHandler(ErrorHandler):
    """
    Master StdErr class that handles a number of common errors
    that occur during Cp2k runs with error messages only in
    the standard error.

    These issues are generally not cp2k-specific, and have to do
    with hardware/slurm/memory/etc.

    This handler does not raise a runtime error, because if the
    error is non-recoverable, then cp2k will stop itself.
    """

    is_monitor = True
    raises_runtime_error = False

    error_msgs = {"seg_fault": ["SIGSEGV"], "out_of_memory": ["insufficient virtual memory"], "abort": ["SIGABRT"]}

    def __init__(self, std_err="std_err.txt"):
        """Initialize the handler with the output file to check.

        Args:
            std_err (str): This is the file where the stderr for cp2k
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.cp2k.jobs.Cp2kJob`.
        """
        self.std_err = std_err
        self.errors = set()

    def check(self, directory="./"):
        """Check for error in std_err file."""
        self.errors = set()
        with open(self.std_err) as file:
            for line in file:
                line = line.strip()
                for err, msgs in StdErrHandler.error_msgs.items():
                    for msg in msgs:
                        if line.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self, directory="./"):
        """Log error, perform no corrections."""
        return {"errors": [f"System error(s): {self.errors}"], "actions": []}


class UnconvergedScfErrorHandler(ErrorHandler):
    """
    CP2K ErrorHandler class that addresses SCF non-convergence.

    SCF convergence can be broken into different categories, depending on the method
    used to solve it. CP2K supports several, and this handler recognizes the following:

    (1) Orbital Transformation Scheme

        CP2K's flagshop SCF solver. These things can be modified to improve convergence:

            (i) Minimizer: Easiest way to do is to move from a fast second order optimizer
                to a first order optimizer: DIIS -> 2 point Conjugate gradient -> 3 point
                CG. Beyond changing the minimizer itself, one can reduce stepsize for
                the minimizer, though CP2K has good defaults.
            (ii) Preconditioner: The preconditioners can aid in accelerating convergence,
                although most work perfectly fine for a wide variety of systems. FULL_ALL
                is "best" from a theoretical perspective, FULL_SINGLE_INVERSE. Separate from
                this is whether to use a preconditioner with the occupation numbers (FD smearing).
                Should be used with rotational constraints removed.
            (iii) Algorithm: Standard algorithm enforces strict orthogonality, but one
                can also use Iterative Refinement of the approximate congruency
                transformation.
            (iv) Once can enable rotations of the occupied subspace which allows
                fractional occupations with  OT. As of October 2021, this option cannot
                be used with 3 point CG, FULL_ALL, or FULL_SINGLE_INVERSE.

    (2) Traditional Diagonalization:

        The standard way to solve the scf procedure is to diagonalize the density matrix.
        This handler implements (roughly) the same procedures for aiding convergence
        as the original vasp handler. CP2K has less functionality for diagonalization, but
        there are some options for charge density mixing. Procedure generally follows:

            (i) Set basic alpha and beta (see docs) with broyden mixing and some small smearing
            (ii) decrease alpha
            (iii) Increase damping (beta) to suppress charge sloshing
            (iv) TODO possible switch mixing method

    (3) Pseudo-diagonalization (Not implemented)

    (4) Purification methods (Not implemented)
    """

    is_monitor = True

    def __init__(self, input_file="cp2k.inp", output_file="cp2k.out"):
        """Initialize the error handler from a set of input and output files.

        Args:
            input_file (str): Name of the CP2K input file.
            output_file (str): Name of the CP2K output file.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.outdata = None
        self.errors = None
        self.scf = None
        self.restart = None

    def check(self, directory="./"):
        """Check output file for failed SCF convergence."""
        # Checks output file for errors.
        out = Cp2kOutput(os.path.join(directory, self.output_file), auto_load=False, verbose=False)
        out.convergence()
        ci = Cp2kInput.from_file(zpath(os.path.join(directory, self.input_file)))
        self.is_ot = ci.check("FORCE_EVAL/DFT/SCF/OT")
        if out.filenames.get("restart"):
            self.restart = out.filenames["restart"][-1]

        # General catch for SCF not converged
        # TODO: should not-static runs allow for some unconverged scf? Leads to issues in my experience
        scf = out.data["scf_converged"] or [True]
        if not scf[0]:
            return True
        return False

    def correct(self, directory="./"):
        """Apply corrections to aid convergence if possible."""
        ci = Cp2kInput.from_file(os.path.join(directory, self.input_file))

        actions = self.__correct_ot(ci=ci) if self.is_ot else self.__correct_diag(ci=ci)

        restart(actions, os.path.join(directory, self.output_file), os.path.join(directory, self.input_file))
        Cp2kModder(ci=ci, filename=self.input_file, directory=directory).apply_actions(actions)
        return {"errors": ["Non-converging Job"], "actions": actions}

    def __correct_ot(self, ci):
        """Apply corrections to OT calculation, if possible."""
        actions = []
        minimizer = (
            ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("MINIMIZER", Keyword("MINIMIZER", "DIIS")).values[0].upper()
        )
        algo = ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("ALGORITHM", Keyword("ALGORITHM", "STRICT")).values[0].upper()
        rotate = ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("ROTATION", Keyword("ROTATION", False)).values[0]
        stepsize = ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("STEPSIZE", Keyword("STEPSIZE", 0.08)).values[0]

        # Try going from DIIS -> CG (slower, but more robust)
        if minimizer == "DIIS":
            actions += [
                {
                    "dict": self.input_file,
                    "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"MINIMIZER": "CG"}}}}}},
                }
            ]

        # Try going from 2pnt to 3pnt line search (slower, but more robust)
        elif minimizer == "CG":
            if (
                ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("LINESEARCH", Keyword("LINESEARCH", "2PNT")).values[0].upper()
                != "3PNT"
                and not rotate
            ):
                actions += [
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"LINESEARCH": "3PNT"}}}}}},
                    }
                ]
            elif ci["FORCE_EVAL"]["DFT"]["SCF"].get("MAX_SCF", Keyword("MAX_SCF", 50)).values[0] < 50:
                actions += [
                    {
                        "dict": self.input_file,
                        "action": {
                            "_set": {
                                "FORCE_EVAL": {
                                    "DFT": {
                                        "SCF": {"MAX_SCF": 50, "OUTER_SCF": {"MAX_SCF": 8}},
                                    }
                                }
                            }
                        },
                    }
                ]

        """
        Switch to more robust OT framework.
        No strict orthogonality of MOs. Use iterative refinement polynomial expansion for orthogonality
        Allow for rotations (i.e., allowing for fractional occupations)
        Rotation requires and 2pnt line search
        Preconditioning on fractional occupation would be preferred but not allowed with FSI precond.
        Increase SCF steps in one loop and decrease outer loops
        """
        if not actions and (algo == "STRICT" or not rotate):
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set": {
                            "FORCE_EVAL": {
                                "DFT": {
                                    "SCF": {
                                        "MAX_SCF": 50,
                                        "OT": {
                                            "LINESEARCH": "2PNT",
                                            "ROTATION": True,
                                            "PRECONDITIONER": "FULL_SINGLE_INVERSE",
                                            "OCCUPATION_PRECONDITIONER": False,
                                            "ALGORITHM": "IRAC",
                                        },
                                        "OUTER_SCF": {"MAX_SCF": 20},
                                    }
                                }
                            }
                        }
                    },
                }
            )

        """
        Beyond the method above, the only thing left to try is decreasing the stepsize a bit.
        Stepsize is 0.15 by default for all but the FSI preconditioner, which uses .08
        """
        if not actions and stepsize > 0.05:
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set": {
                            "FORCE_EVAL": {
                                "DFT": {
                                    "SCF": {
                                        "OT": {
                                            "STEPSIZE": 0.05,
                                        }
                                    }
                                }
                            }
                        }
                    },
                }
            )

        return actions

    def __correct_diag(self, ci):
        """Apply corrections to diagonalization calculation, if possible."""
        actions = []

        if not ci.check("FORCE_EVAL/DFT/SCF/MIXING"):
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set": {
                            "FORCE_EVAL": {
                                "DFT": {
                                    "SCF": {
                                        "MIXING": {
                                            "METHOD": "BROYDEN_MIXING",
                                            "ALPHA": 0.1,
                                        }
                                    }
                                }
                            }
                        }
                    },
                }
            )

        else:
            alpha = ci["FORCE_EVAL"]["DFT"]["SCF"]["MIXING"].get("ALPHA", Keyword("ALPHA", 0.2)).values[0]
            beta = ci["FORCE_EVAL"]["DFT"]["SCF"]["MIXING"].get("BETA", Keyword("BETA", 0.01)).values[0]
            nbuffer = ci["FORCE_EVAL"]["DFT"]["SCF"]["MIXING"].get("NBUFFER", Keyword("NBUFFER", 4)).values[0]

            if nbuffer < 20:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {
                            "_set": {
                                "FORCE_EVAL": {
                                    "DFT": {
                                        "SCF": {
                                            "MIXING": {
                                                "NBUFFER": 20,
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    }
                )

            if alpha > 0.05:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MIXING": {"ALPHA": 0.05, "BETA": 0.01}}}}}},
                    }
                )

            elif alpha > 0.01:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MIXING": {"ALPHA": 0.01, "BETA": 0.01}}}}}},
                    }
                )

            elif alpha > 0.005:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {
                            "_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MIXING": {"ALPHA": 0.005, "BETA": 0.01}}}}}
                        },
                    }
                )

            elif beta < 1:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MIXING": {"ALPHA": 0.005, "BETA": 3}}}}}},
                    }
                )

        if not ci.check("FORCE_EVAL/DFT/SCF/SMEAR"):
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set": {
                            "FORCE_EVAL": {
                                "DFT": {
                                    "SCF": {"ADDED_MOS": 1000, "SMEAR": {"ELEC_TEMP": 300, "METHOD": "FERMI_DIRAC"}}
                                }
                            }
                        }
                    },
                }
            )

        return actions


class DivergingScfErrorHandler(ErrorHandler):
    """
    CP2K ErrorHandler that detects if calculation is diverging. This is
    done by seeing if, on average, the last 10 convergence print outs were
    increasing rather than decreasing.

    Diverging SCF usually comes from issues outside the scope of
    custodian such as unphysical atomic coordinates. However, a system
    with a very high condition number for the overlap matrix (see
    FORCE_EVAL/DFT/PRINT/CONDITION_OVERLAP) can diverge if the precision
    is set to a normal value. So, this error handler will bump up the precision
    in an attempt to remedy the problem.
    """

    is_monitor = True

    def __init__(self, output_file="cp2k.out", input_file="cp2k.inp"):
        """Initializes the error handler from an output files.

        Args:
            output_file (str): Name of the CP2K output file.
            input_file (str): Name of the CP2K input file.
        """
        self.output_file = output_file
        self.input_file = input_file

    def check(self, directory="./"):
        """Check for diverging SCF."""
        conv = get_conv(os.path.join(directory, self.output_file))
        tmp = np.diff(conv[-10:])
        return len(conv) > 10 and all(_ > 0 for _ in tmp) and any(_ > 1 for _ in conv)

    def correct(self, directory="./"):
        """Correct issue if possible."""
        ci = Cp2kInput.from_file(os.path.join(directory, self.input_file))
        actions = []

        p = ci["force_eval"]["dft"]["qs"].get("EPS_DEFAULT", Keyword("EPS_DEFAULT", 1e-10)).values[0]
        if p > 1e-16:
            actions.append(
                {"dict": self.input_file, "action": {"_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_DEFAULT": 1e-16}}}}}}
            )
        p = ci["force_eval"]["dft"]["qs"].get("EPS_PGF_ORB", Keyword("EPS_PGF_ORB", np.sqrt(p))).values[0]
        if p > 1e-12:
            actions.append(
                {"dict": self.input_file, "action": {"_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_PGF_ORB": 1e-12}}}}}}
            )
        Cp2kModder(ci=ci, filename=self.input_file, directory=directory).apply_actions(actions)
        return {"errors": ["Diverging SCF"], "actions": actions}


class FrozenJobErrorHandler(ErrorHandler):
    """
    Detects an error when the output file has not been updated
    in timeout seconds.

    3 types of frozen jobs are considered:

        (1) Frozen preconditioner: in rare cases, the preconditioner
            can get stuck. This has been noticed for the FULL_SINGLE_INVERSE
            preconditioner, and so this handler will try first switching
            to FULL_ALL, and otherwise change the preconditioner solver
            from default to direct
        (2) Frozen SCF: CP2K can get stuck in the scf loop itself. Reasons
            for this cannot be determined by the handler, but since the scf
            steps have timings, it is easier to diagnose. This handler will
            determine if there has been at least 2 steps in the current scf
            loop (so that preconditioner is not included), and then check to see
            if the file has not been updated in 4 times the last scf loop time.
        (3) General frozen: CP2K hangs for some other, unknown reason. Experience
            has shown this can be a hardware issue. Timeout for this is quite large
            as some sub-routines, like the HFX module, can take a long time to
            update the output file.

    """

    is_monitor = True

    def __init__(self, input_file="cp2k.inp", output_file="cp2k.out", timeout=3600):
        """Initialize the handler with the output file to check.

        Args:
            input_file (str): Name of the input file to modify if needed
            output_file (str): Name of the output file to monitor
            timeout (int): The time in seconds between checks where if there
                is no activity on the output file, the run is considered
                frozen. Defaults to 3600 seconds, i.e., 1 hour. Most stages of
                cp2k take much less than 1 hour, but 1 hour is the default to account
                for large HF force calculations or sizable preconditioner calculations.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.timeout = timeout
        self.frozen_preconditioner = False
        self.restart = None

    def check(self, directory="./"):
        """Check for frozen jobs."""
        st = os.stat(os.path.join(directory, self.output_file))
        out = Cp2kOutput(os.path.join(directory, self.output_file), auto_load=False, verbose=False)
        try:
            out.ran_successfully()
            # If job finished, then hung, don't need to wait very long to confirm frozen
            if time.time() - st.st_mtime > 300:
                return True
            return False
        except ValueError:
            pass

        t = tail(self.output_file, 2)
        if time.time() - st.st_mtime > self.timeout:
            if t[0].split() == ["Step", "Update", "method", "Time", "Convergence", "Total", "energy", "Change"]:
                self.frozen_preconditioner = True
            return True

        return False

    def correct(self, directory="./"):
        """Correct issue if possible."""
        ci = Cp2kInput.from_file(os.path.join(directory, self.input_file))
        actions = []
        errors = []

        if self.frozen_preconditioner:
            if ci.check("FORCE_EVAL/DFT/SCF/OT"):
                p = ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("PRECONDITIONER", Keyword("PRECONDITIONER", "FULL_ALL"))

                if p == Keyword("PRECONDITIONER", "FULL_SINGLE_INVERSE"):
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set": {"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"PRECONDITIONER": "FULL_ALL"}}}}}
                            },
                        }
                    )

                else:
                    p = ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"].get("PRECOND_SOLVER", Keyword("PRECOND_SOLVER", "DEFAULT"))
                    if p.values[0] == "DEFAULT":
                        actions.append(
                            {
                                "dict": self.input_file,
                                "action": {
                                    "_set": {"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"PRECOND_SOLVER": "DIRECT"}}}}}
                                },
                            }
                        )

            elif ci.check("FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON"):
                p = ci.by_path("FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON").get(
                    "PRECONDITIONER", Keyword("PRECONDITIONER", "FULL_ALL")
                )

                if p == Keyword("PRECONDITIONER", "FULL_SINGLE_INVERSE"):
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {"DIAGONALIZATION": {"DAVIDSON": {"PRECONDITIONER": "FULL_ALL"}}}
                                        }
                                    }
                                }
                            },
                        }
                    )

                else:
                    p = ci.by_path("FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON").get(
                        "PRECOND_SOLVER", Keyword("PRECOND_SOLVER", "DEFAULT")
                    )
                    if p.values[0] == "DEFAULT":
                        actions.append(
                            {
                                "dict": self.input_file,
                                "action": {
                                    "_set": {
                                        "FORCE_EVAL": {
                                            "DFT": {
                                                "SCF": {"DIAGONALIZATION": {"DAVIDSON": {"PRECOND_SOLVER": "DIRECT"}}}
                                            }
                                        }
                                    }
                                },
                            }
                        )

            self.frozen_preconditioner = False
            errors.append("Frozen preconditioner")

        else:
            errors.append("Frozen job")

        restart(actions, os.path.join(directory, self.output_file), os.path.join(self.input_file))
        Cp2kModder(ci=ci, filename=self.input_file, directory=directory).apply_actions(actions)
        return {"errors": errors, "actions": actions}


class AbortHandler(ErrorHandler):
    """Handles errors that cp2k recognizes internally.

    These internal errors cause a kill-signal, as opposed to things like slow scf
    convergence, which is an unwanted feature of optimization rather than an error per se.
    Currently this error handler recognizes the following:

        (1) Cholesky decomposition error in preconditioner. If this is found, the
            handler will try switching between Full_all/Full_single_inverse
            preconditioner and increasing precision.

        (2) Cholesky decomposition error from SCF diagonalization. If found, the
            handler will try switching from the restore algorithm to inverse cholesky
    """

    is_monitor = False
    is_terminating = True

    def __init__(self, input_file="cp2k.inp", output_file="cp2k.out"):
        """
        Initialize handler for CP2K abort messages.

        Args:
            input_file: (str) name of the input file
            output_file: (str) name of the output file
        """
        self.input_file = input_file
        self.output_file = output_file
        self.messages = {
            "cholesky": r"(Cholesky decomposition failed. Matrix ill conditioned ?)",
            "cholesky_scf": r"(Cholesky decompose failed: the matrix is not positive definite or)",
        }
        self.responses = []

    def check(self, directory="./"):
        """Check for abort messages."""
        matches = regrep(
            os.path.join(directory, self.output_file),
            patterns=self.messages,
            reverse=True,
            terminate_on_match=True,
            postprocess=str,
        )
        for match in matches:
            self.responses.append(match)
            return True
        return False

    def correct(self, directory="./"):
        """Correct issue if possible."""
        ci = Cp2kInput.from_file(os.path.join(directory, self.input_file))
        actions = []

        if self.responses[-1] == "cholesky":
            n = self.responses.count("cholesky")
            if n == 1:
                # Change preconditioner
                p = (
                    ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]
                    .get("PRECONDITIONER", Keyword("PRECONDITIONER", "FULL_ALL"))
                    .values[0]
                )

                if p == "FULL_ALL":
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set": {
                                    "FORCE_EVAL": {"DFT": {"SCF": {"OT": {"PRECONDITIONER": "FULL_SINGLE_INVERSE"}}}}
                                }
                            },
                        }
                    )
                elif p == "FULL_SINGLE_INVERSE":
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set": {"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"PRECONDITIONER": "FULL_ALL"}}}}}
                            },
                        }
                    )

            if n == 2:
                # preconditioner was fine, make sure eps_default is at least 1e-12
                p = ci["force_eval"]["dft"]["qs"].get("EPS_DEFAULT", Keyword("EPS_DEFAULT", 1e-12)).values[0]
                if p > 1e-12:
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {"_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_DEFAULT": 1e-12}}}}},
                        }
                    )
                else:
                    n += 1

            if n == 3:
                # bump up overlap matrix resolution
                eps_default = ci["force_eval"]["dft"]["qs"].get("EPS_DEFAULT", Keyword("EPS_DEFAULT", 1e-12)).values[0]
                p = (
                    ci["force_eval"]["dft"]["qs"]
                    .get("EPS_PGF_ORB", Keyword("EPS_PGF_ORB", np.sqrt(eps_default)))
                    .values[0]
                )
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {
                            "_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_PGF_ORB": 1e-10 if p > 1e-10 else p / 10}}}}
                        },
                    }
                )

            if n == 4 and ci["force_eval"]["dft"].get("wfn_restart_file_name"):
                # restart file could be problematic (gga restart for hybrids)
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {
                            "_unset": {"FORCE_EVAL": {"DFT": "WFN_RESTART_FILE_NAME"}},
                            "_set": {
                                "FORCE_EVAL": {
                                    "DFT": {
                                        "XC": {
                                            "HF": {
                                                "SCREENING": {
                                                    "SCREEN_ON_INITIAL_P": False,
                                                    "SCREEN_P_FORCES": False,
                                                },
                                            }
                                        }
                                    }
                                }
                            },
                        },
                    }
                )

        elif self.responses[-1] == "cholesky_scf":
            n = self.responses.count("cholesky_scf")
            if n == 1:
                p = ci["FORCE_EVAL"]["DFT"]["SCF"].get("CHOLESKY", Keyword("CHOLESKY", "RESTORE")).values[0]

                if p == "RESTORE":
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"CHOLESKY": "INVERSE"}}}}},
                        }
                    )

        restart(actions, os.path.join(directory, self.output_file), os.path.join(self.input_file))
        Cp2kModder(ci=ci, filename=self.input_file, directory=directory).apply_actions(actions)
        return {"errors": [self.responses[-1]], "actions": actions}


class NumericalPrecisionHandler(ErrorHandler):
    """This handler detects convergence cycles getting stuck due to numerical imprecision.

    CP2K offers lots of functionality for decreasing numerical precision in order to
    speed-up calculations. This can unfortunately lead to convergence cycles getting 'stuck'.
    While it can be hard to separate numerical issues from things like optimizer choice,
    slow-to-converge systems, or divergence issues, this handler specifically detects the
    problem of convergence getting stuck, where the same convergence value is returned many
    times in a row. (Numerical precision can also be the cause of oscillating convergence.
    This is a little harder to assess, as it can also just look like slow-convergence.)
    Currently, we have identified the following causes of this problem:

        (1) EPS_DEFAULT: Sets the overall precision of the Quickstep module (note, not
            the same as EPS_SCF). The CP2K default of 1e-10 works fine for simple systems
            but will almost certainly fail for open-shell or defective systems. 1e-12 is
            recommended, with some applications needing 1e-14. The handler will reduce
            eps_default until 1e-16, at which point its probably something else causing the
            problem.

        (2) XC_GRID: The default xc grid is usually sufficient, but some systems with strong
            correlation have been found to require the finer grid.

        (3) HF Screening: The numerical approximations used to speed up hybrid calculations
            can lead to imprecision. EPS_SCHWARZ should usually be at least 1e-7, for example.

        (4) ADMM Basis: When using admm, the polarization term being neglected can sometimes
            lead to issues.

        (5) "Fake" numerical precision error due to DIIS optimizer: it has been found that
            in some systems, OT with the second-order DIIS optimizer will hope around the minimum
            and report the same value, giving the impression that the issue is numerical
            precision, when actually it is an SCF/SCF-optimizer problem. This one is rather
            nefarious because it is hard to separate the two. At present, the best solution is
            to simply go to the CG algorithm by default when the problem is recognized to
            alleviate this.
    """

    is_monitor = True

    def __init__(
        self,
        input_file="cp2k.inp",
        output_file="cp2k.out",
        max_same=5,
        pgf_orb_strict=1e-20,
        eps_default_strict=1e-12,
        eps_gvg_strict=1e-10,
    ):
        """
        Initialize the error handler.

        Args:
            input_file (str): name of the input file to modify (if needed)
            output_file (str): name of the output file to monitor
            max_same (int): maximum number of SCF convergence loops with the same
                convergence value before numerical imprecision is decided. It only
                checks for consecutive convergence values, so if you have:

                    Convergence
                        0.0001
                        0.0001
                        0.0001

                This will be caught and corrected, but it won't catch instances where the
                last n-1 convergence values are the same for each outer scf loop, but it gets
                reset by the preconditioner.
            pgf_orb_strict (float): TODO @janosh someone who knows this code, please add a description
            eps_default_strict (float): TODO @janosh likewise
            eps_gvg_strict (float): TODO @janosh likewise
        """
        self.input_file = input_file
        self.output_file = output_file
        self.max_same = max_same
        self.overlap_condition = None
        self.pgf_orb_strict = pgf_orb_strict
        self.eps_default_strict = eps_default_strict
        self.eps_gvg_strict = eps_gvg_strict

    def check(self, directory="./"):
        """Check for stuck SCF convergence."""
        conv = get_conv(os.path.join(directory, self.output_file))
        counts = [len([*group]) for _k, group in itertools.groupby(conv)]
        if any(cnt > self.max_same for cnt in counts):
            return True
        return False

    def correct(self, directory="/."):
        """Correct issue if possible."""
        ci = Cp2kInput.from_file(os.path.join(directory, self.input_file))
        actions = []

        if ci.check("FORCE_EVAL/DFT/XC/HF"):  # Hybrid has special considerations
            if ci.check("FORCE_EVAL/DFT/XC/HF/SCREENING"):
                eps_schwarz = (
                    ci.by_path("FORCE_EVAL/DFT/XC/HF/SCREENING")
                    .get("EPS_SCHWARZ", Keyword("EPS_SCHWARZ", 1e-10))
                    .values[0]
                )
                if eps_schwarz > 1e-7:
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set": {"FORCE_EVAL": {"DFT": {"XC": {"HF": {"SCREENING": {"EPS_SCHWARZ": 1e-7}}}}}}
                            },
                        }
                    )

            m = regrep(
                self.output_file,
                patterns={"PGF": re.compile(r"WARNING in hfx_energy_potential.F:592 :: The Kohn Sham matrix is not")},
            )
            eps_default = ci.by_path("FORCE_EVAL/DFT/QS").get("EPS_DEFAULT", Keyword("EPS_DEFAULT", 1e-10)).values[0]
            pgf = (
                ci["force_eval"]["dft"]["qs"].get("EPS_PGF_ORB", Keyword("EPS_PGF_ORB", np.sqrt(eps_default))).values[0]
            )
            if m.get("PGF") and pgf > self.pgf_orb_strict:
                actions.append(self.__set_pgf_orb())

        # If no hybrid modifications were performed
        if len(actions) == 0:
            # Overall precision
            eps_default = ci.by_path("FORCE_EVAL/DFT/QS").get("EPS_DEFAULT", Keyword("", 1e-10)).values[0]

            # overlap matrix precision
            pgf = ci["force_eval"]["dft"]["qs"].get("EPS_PGF_ORB", Keyword("", np.sqrt(eps_default))).values[0]

            # realspace KS matrix precision
            gvg = ci["force_eval"]["dft"]["qs"].get("EPS_GVG_RSPACE", Keyword("", np.sqrt(eps_default))).values[0]

            if ci.check("force_eval/dft/scf/ot"):
                minimizer = ci["force_eval"]["dft"]["scf"]["ot"].get_keyword("minimizer", Keyword("", "CG")).values[0]

                if minimizer.upper() == "DIIS" or minimizer.upper() == "BROYDEN":
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"MINIMIZER": "CG"}}}}}},
                        }
                    )

            if eps_default > self.eps_default_strict:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_DEFAULT": self.eps_default_strict}}}}},
                    }
                )

            if pgf > self.pgf_orb_strict:
                actions.append(self.__set_pgf_orb())

            if gvg > self.eps_gvg_strict:
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_GVG_RSPACE": self.eps_gvg_strict}}}}},
                    }
                )

            if not actions and (
                not ci.check("FORCE_EVAL/DFT/XC/XC_GRID")
                or not ci.by_path("FORCE_EVAL/DFT/XC/XC_GRID").get("USE_FINER_GRID", False)
            ):
                # Try a more expensive XC grid
                actions.append(
                    {
                        "dict": self.input_file,
                        "action": {"_set": {"FORCE_EVAL": {"DFT": {"XC": {"XC_GRID": {"USE_FINER_GRID": True}}}}}},
                    }
                )

        restart(actions, os.path.join(directory, self.output_file), os.path.join(self.input_file))
        Cp2kModder(ci=ci, filename=self.input_file, directory=directory).apply_actions(actions)
        return {"errors": ["Insufficient precision"], "actions": actions}

    def __set_pgf_orb(self):
        """Helper function to set the PGF_ORB keyword."""
        return {
            "dict": self.input_file,
            "action": {"_set": {"FORCE_EVAL": {"DFT": {"QS": {"EPS_PGF_ORB": self.pgf_orb_strict}}}}},
        }


class UnconvergedRelaxationErrorHandler(ErrorHandler):
    """
    This handler checks to see if geometry optimization has failed to converge,
    as signified by a line in the output file that says the maximum number of optimization
    steps were reached.

    By, this handler works by jumping back-and-forth between BFGS and CG optimizers. BFGS
    is fast, but unstable when far from the minimum, while CG is slow (and even grows slower as
    it approaches the minimum) but robust. By switching back and forth, we have found that
    overall convergence can be accelerated.
    """

    is_monitor = True

    def __init__(
        self,
        input_file="cp2k.inp",
        output_file="cp2k.out",
        max_iter=20,
        max_total_iter=200,
        optimizers=("BFGS", "CG", "BFGS", "CG"),
    ):
        """
        Initialize the error handler.

        Args:
            input_file: name of the input file
            output_file: name of the output file
            max_iter: Max iter for an "inner loop", i.e. max iterations for one optimizer before
                switching to another.
            max_total_iter: max total number of iterations before calling it quits.
                (Not reached if custodian runs out of things to try on the inner loops)
            optimizers: Which optimizers to try with custodian. Can be used to go back and forth,
                e.g. Try BFGS then CG then BFGS again for 20 iterations each until the max total
                iterations is reached.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.max_iter = max_iter
        self.max_total_iter = max_total_iter
        self.optimizers = optimizers
        self.optimizer_id = 0

    def check(self, directory="./"):
        """Check for unconverged geometry optimization."""
        o = Cp2kOutput(os.path.join(directory, self.output_file))
        o.convergence()
        if o.data.get("geo_opt_not_converged"):
            return True
        return False

    def correct(self, directory):
        """Correct issue if possible."""
        ci = Cp2kInput.from_file(os.path.join(directory, self.input_file))
        actions = []

        max_iter = ci["motion"]["geo_opt"].get("MAX_ITER", Keyword("", 200)).values[0]
        optimizer = ci["motion"]["geo_opt"].get("OPTIMIZER", Keyword("OPTIMIZER", "BFGS")).values[0].upper()

        # If list of optimizers includes the starting condition, iterate past it
        if optimizer == self.optimizers[self.optimizer_id]:
            self.optimizer_id += 1

        if max_iter + self.max_iter > self.max_total_iter:
            return {"errors": ["Unsuccessful relaxation"], "actions": []}
        if self.optimizer_id >= len(self.optimizers):
            return {"errors": ["Unsuccessful relaxation"], "actions": []}

        # set optimizer. Ensure CG is 2pnt. 3pnt not fully developed for relaxations
        if ci.check("MOTION/GEO_OPT"):
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set": {
                            "MOTION": {
                                "GEO_OPT": {
                                    "OPTIMIZER": self.optimizers[self.optimizer_id],
                                    "MAX_ITER": max_iter + self.max_iter,
                                    "CG": {"LINE_SEARCH": {"TYPE": "2PNT"}},
                                }
                            }
                        }
                    },
                }
            )

        self.optimizer_id += 1
        restart(actions, os.path.join(directory, self.output_file), os.path.join(self.input_file))
        Cp2kModder(ci=ci, filename=self.input_file, directory=directory).apply_actions(actions)
        return {"errors": ["Unsuccessful relaxation"], "actions": actions}


class WalltimeHandler(ErrorHandler):
    """
    This walltime error handler, when enabled, will detect whether
    the CP2K internal walltime handler has been tripped. If walltime
    has been reached (plus some buffer), then the walltime handler will create a
    "checkpoint.json" file that enables the job to continue. This is
    different than saving successful runs as custodian.chk.#.tar.gz
    (see Custodian), and simply creates checkpoint.json.
    """

    is_monitor = False
    raises_runtime_error = False
    is_terminating = False

    def __init__(self, output_file="cp2k.out", enable_checkpointing=True):
        """
        Args:
            output_file (str): name of the cp2k output file
            enable_checkpointing (bool): whether or not to enable checkpointing when
                the walltime is reached by dumping checkpoint.json.
        """
        self.output_file = output_file
        self.enable_checkpointing = enable_checkpointing

    def check(self, directory="./"):
        """Check if internal CP2K walltime handler was tripped."""
        if regrep(
            filename=os.path.join(directory, self.output_file),
            patterns={"walltime": r"(exceeded requested execution time)"},
            reverse=True,
            terminate_on_match=True,
            postprocess=bool,
        ).get("walltime"):
            return True
        return False

    def correct(self, directory="./"):
        """Dump checkpoint info if requested."""
        if self.enable_checkpointing:
            dumpfn({"_path": directory}, fn=(os.path.join(directory, "checkpoint.json")))
        return {"errors": ["Walltime error"], "actions": []}
