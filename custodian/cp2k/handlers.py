"""
Error handlers for CP2K calculations.

Handlers should be specific enough that they are not bulky (keep overhead low),
but if two handlers will always be called together, then consider joining them
into one handler.

When adding more remember the following tips:
(1) Handlers return True when the error is caught, and false if no error was caught
(2) CP2K error handlers will be different from VASP error handlers depending on if
    you are using Cp2k-specific functionality (like OT minimization).
(3) Not all things that could go wrong should be handled by custodian. For example
    walltime handling can be done natively in CP2K, and will have added benefits like
    writing a wavefunction restart file before quiting.
"""

import numpy as np
import os
import time
from typing import Sequence
import itertools
import re
from pymatgen.io.cp2k.inputs import Cp2kInput, Keyword
from pymatgen.io.cp2k.outputs import Cp2kOutput
from pymatgen.io.cp2k.utils import get_aux_basis
from custodian.custodian import ErrorHandler
from custodian.cp2k.interpreter import Cp2kModder
from custodian.cp2k.utils import restart, tail, get_conv
from monty.re import regrep
from monty.os.path import zpath
from monty.serialization import dumpfn

__author__ = "Nicholas Winner"
__version__ = "0.9"
__email__ = "nwinner@berkeley.edu"
__date__ = "March 2021"


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

    error_msgs = {
        "seg_fault": ["SIGSEGV"],
        "out_of_memory": ["insufficient virtual memory"],
        "ORTE": ["ORTE"],
        "abort": ["SIGABRT"]
    }

    def __init__(self, output_file='cp2k.out', std_err="std_err.txt"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_file (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.cp2k.jobs.Cp2kJob`.
        """
        self.std_err = std_err
        self.output_file = output_file
        self.errors = set()

    def check(self):
        self.errors = set()
        with open(self.std_err, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in StdErrHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        return {"errors": ["System error(s): {}".format(self.errors)], "actions": []}


class UnconvergedScfErrorHandler(ErrorHandler):
    """
    CP2K ErrorHandler class that addresses SCF non-convergence.
    """

    is_monitor = True

    def __init__(self,
                 input_file="cp2k.inp",
                 output_file="cp2k.out",
                 scf_max_cycles=200):
        """
        Initializes the error handler from a set of input and output files.

        Args:
            input_file (str): Name of the CP2K input file.
            output_file (str): Name of the CP2K output file.
            scf_max_cycles (int): The max iterations to set to fix SCF failure.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.scf_max_cycles = scf_max_cycles
        self.outdata = None
        self.errors = None
        self.scf = None
        self.restart = None
        self.mixing_hierarchy = ['BROYDEN_MIXING', 'BROYDEN_MIXING_LINEAR', 'PULAY_MIXING', 'PULAY_MIXING_LINEAR']
        if os.path.exists(zpath(self.input_file)):
            ci = Cp2kInput.from_file(zpath(self.input_file))
            if ci['GLOBAL']['RUN_TYPE'].values[0].__str__().upper() in [
                "ENERGY", "ENERGY_FORCE", "WAVEFUNCTION_OPTIMIZATION", "WFN_OPT"]:
                self.is_static = True
            else:
                self.is_static = False
            self.is_ot = True if ci.check('FORCE_EVAL/DFT/SCF/OT') else False
            if ci.check('FORCE_EVAL/DFT/SCF/MIXING'):
                method = ci.by_path(
                    'FORCE_EVAL/DFT/SCF/MIXING'
                ).get('METHOD', Keyword('METHOD', 'DIRECT_P_MIXING')).values[0]
                alpha = ci.by_path(
                    'FORCE_EVAL/DFT/SCF/MIXING'
                ).get('ALPHA', Keyword('ALPHA', .4)).values[0]
                beta = ci.by_path(
                    'FORCE_EVAL/DFT/SCF/MIXING'
                ).get('BETA', Keyword('BETA', .5)).values[0]
                ext = '_LINEAR' if (beta > 1 and alpha < .1) else ''
                self.mixing_hierarchy = [
                    m for m in self.mixing_hierarchy if m != method.upper()+ext
                ]

    def check(self):
        # Checks output file for errors.
        out = Cp2kOutput(self.output_file, auto_load=False, verbose=False)
        out.convergence()
        if out.filenames.get('restart'):
            self.restart = out.filenames['restart'][-1]

        # General catch for SCF not converged
        # If not static, mark not-converged if last 5 SCF loops
        # failed to converge
        scf = out.data['scf_converged'] or [True]
        if not scf[0]:
            return True
        return False

    # TODO More comprehensive mixing methods for non-OT diagonalization
    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = []

        if self.is_ot:

            if ci['FORCE_EVAL']['DFT']['SCF']['OT'].get(
                    'MINIMIZER', Keyword('MINIMIZER', 'DIIS')
            ).values[0].upper() == 'DIIS':
                actions.append({'dict': self.input_file,
                                "action": {"_set": {
                                    'FORCE_EVAL': {
                                        'DFT': {
                                            'SCF': {
                                                'OT': {
                                                    'MINIMIZER': 'CG'
                                                }
                                            }
                                        }
                                    }
                                }}})
            elif ci['FORCE_EVAL']['DFT']['SCF']['OT'].get(
                    'MINIMIZER', Keyword('MINIMIZER', 'DIIS')
            ).values[0].upper() == 'CG':
                if ci['FORCE_EVAL']['DFT']['SCF']['OT'].get(
                        'LINESEARCH', Keyword('LINESEARCH', '2PNT')
                ).values[0].upper() != '3PNT':
                    actions.append({'dict': self.input_file,
                                    "action": {"_set": {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'SCF': {
                                                    'OT': {
                                                        'LINESEARCH': '3PNT'
                                                    }
                                                }
                                            }
                                        }
                                    }}})
                elif ci['FORCE_EVAL']['DFT']['SCF'].get(
                            'MAX_SCF', Keyword('MAX_SCF', 50)
                        ).values[0] < 50:
                        actions.append({'dict': self.input_file,
                                        "action": {"_set": {
                                            'FORCE_EVAL': {
                                                'DFT': {
                                                    'SCF': {
                                                        'MAX_SCF': 50,
                                                        'OUTER_SCF': {
                                                            'MAX_SCF': 8
                                                        }
                                                    },
                                                }
                                            }
                                        }}})
        else:
            # Make sure mixing and smearing are enabled
            # Try Broyden -> Pulay mixing

            if not ci.check('FORCE_EVAL/DFT/SCF/MIXING'):
                actions.append({'dict': self.input_file,
                                'action': {"_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {
                                                "MIXING": {
                                                    'METHOD': 'BROYDEN_MIXING',
                                                    'ALPHA': 0.1,
                                                }
                                            }
                                        }
                                    }
                                }}})

            else:
                alpha = ci['FORCE_EVAL']['DFT']['SCF']['MIXING'].get('ALPHA', Keyword('ALPHA', 0.2)).values[0]
                beta = ci['FORCE_EVAL']['DFT']['SCF']['MIXING'].get('BETA', Keyword('BETA', 0.01)).values[0]
                nbuffer = ci['FORCE_EVAL']['DFT']['SCF']['MIXING'].get('NBUFFER', Keyword('NBUFFER', 4)).values[0]

                if nbuffer < 20:
                    actions.append({'dict': self.input_file,
                                    'action': {"_set": {
                                        "FORCE_EVAL": {
                                            "DFT": {
                                                "SCF": {
                                                    "MIXING": {
                                                        "NBUFFER": 20,
                                                    }
                                                }
                                            }
                                        }
                                    }}})

                if alpha > .05:
                    actions.append({'dict': self.input_file,
                                    'action': {"_set": {
                                        "FORCE_EVAL": {
                                            "DFT": {
                                                "SCF": {
                                                    "MIXING": {
                                                        "ALPHA": 0.05,
                                                        "BETA": 0.01
                                                    }
                                                }
                                            }
                                        }
                                    }}})

                elif alpha > .01:
                    actions.append({'dict': self.input_file,
                                    'action': {"_set": {
                                        "FORCE_EVAL": {
                                            "DFT": {
                                                "SCF": {
                                                    "MIXING": {
                                                        "ALPHA": 0.01,
                                                        "BETA": 0.01
                                                    }
                                                }
                                            }
                                        }
                                    }}})

                elif alpha > .005:
                    actions.append({'dict': self.input_file,
                                    'action': {"_set": {
                                        "FORCE_EVAL": {
                                            "DFT": {
                                                "SCF": {
                                                    "MIXING": {
                                                        "ALPHA": 0.005,
                                                        "BETA": 0.01
                                                    }
                                                }
                                            }
                                        }
                                    }}})

                elif beta < 1:
                    actions.append({'dict': self.input_file,
                                    'action': {"_set": {
                                        "FORCE_EVAL": {
                                            "DFT": {
                                                "SCF": {
                                                    "MIXING": {
                                                        "ALPHA": 0.005,
                                                        "BETA": 3
                                                    }
                                                }
                                            }
                                        }
                                    }}})

            if not ci.check('FORCE_EVAL/DFT/SCF/SMEAR'):
                actions.append({'dict': self.input_file,
                                'action': {"_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {
                                                "SMEAR": {
                                                    "ELEC_TEMP": 500,
                                                    "METHOD": "FERMI_DIRAC"
                                                }
                                            }
                                        }
                                    }
                                }}})

        restart(actions, self.output_file, self.input_file)
        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {"errors": ["Non-converging Job"], "actions": actions}


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

    def __init__(self, output_file="cp2k.out", input_file='cp2k.inp'):
        """
        Initializes the error handler from an output files.

        Args:
            output_file (str): Name of the CP2K output file.
        """
        self.output_file = output_file
        self.input_file = input_file

    def check(self):
        conv = get_conv(self.output_file)
        tmp = np.diff(conv[-10:])
        if len(conv) > 10 and all([_ > 0 for _ in tmp]) and any([_ > 1 for _ in conv]):
            return True
        return False

    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = []

        p = ci['force_eval']['dft']['qs'].get(
            'EPS_DEFAULT',
            Keyword('EPS_DEFAULT', 1e-10)
        ).values[0]
        if p > 1e-16:
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set":
                            {
                                'FORCE_EVAL': {
                                    'DFT': {
                                        'QS': {
                                            'EPS_DEFAULT': 1e-16
                                        }
                                    }
                                }
                            }

                    }
                }
            )
        p = ci['force_eval']['dft']['qs'].get(
            'EPS_PGF_ORB',
            Keyword('EPS_PGF_ORB', np.sqrt(p))
        ).values[0]
        if p > 1e-12:
            actions.append(
                {
                    "dict": self.input_file,
                    "action": {
                        "_set":
                            {
                                'FORCE_EVAL': {
                                    'DFT': {
                                        'QS': {
                                            'EPS_PGF_ORB': 1e-12
                                        }
                                    }
                                }
                            }

                    }
                }
            )
        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {'errors': ['Diverging SCF'], 'actions': actions}


class FrozenJobErrorHandler(ErrorHandler):
    """
    Detects an error when the output file has not been updated
    in timeout seconds.

    3 types of frozen jobs are considered:

        (1) Frozen preconditioner: in rare cases, the preconditioner
            can get stuck. This has been noticed for the FULL_SINGLE_INVERSE
            preconditioner, and so this handler will try first switching
            to FULL_ALL, and otheerwise change the preconditioner solver
            from default to direct
        (2) Frozen SCF: CP2K can get stuck in the scf loop itself. Reasons
            for this cannot be determined by the handler, but since the scf
            steps have timings, it is easier to diagnose. This handler will
            determine if there has been at least 2 steps in the current scf
            loop (so that preconditioner is not included), and then check to see
            if the file has not been updated in 4 times the last scf loop time.
        (3) General frozen: CP2K hangs for some other, unknown reason. Experience
            has shown this can be a hardware issue. Timeout for this is quite large
            as some sub-routines, like ethe HFX module, can take a long time to
            update the output file.

    """

    is_monitor = True

    def __init__(self, input_file="cp2k.inp", output_file="cp2k.out", timeout=3600):
        """
        Initializes the handler with the output file to check.

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

    def check(self):
        st = os.stat(self.output_file)
        out = Cp2kOutput(self.output_file, auto_load=False, verbose=False)
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
            if t[0].split() == ['Step', 'Update', 'method', 'Time', 'Convergence', 'Total', 'energy', 'Change']:
                self.frozen_preconditioner = True
            return True

        return False

    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = []
        errors = []

        if self.frozen_preconditioner:
            if ci.check('FORCE_EVAL/DFT/SCF/OT'):
                p = ci['FORCE_EVAL']['DFT']['SCF']['OT'].get('PRECONDITIONER', Keyword('PRECONDITIONER', 'FULL_ALL'))

                if p == Keyword('PRECONDITIONER', 'FULL_SINGLE_INVERSE'):
                    actions.append({'dict': self.input_file,
                                    "action": {"_set": {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'SCF': {
                                                    'OT': {
                                                        'PRECONDITIONER': 'FULL_ALL'
                                                    }
                                                }
                                            }
                                        }
                                    }}})

                else:
                    p = ci['FORCE_EVAL']['DFT']['SCF']['OT'].get(
                        'PRECOND_SOLVER', Keyword('PRECOND_SOLVER', 'DEFAULT')
                    )
                    if p.values[0] == 'DEFAULT':
                        actions.append({'dict': self.input_file,
                                        "action": {"_set": {
                                            'FORCE_EVAL': {
                                                'DFT': {
                                                    'SCF': {
                                                        'OT': {
                                                            'PRECOND_SOLVER': 'DIRECT'
                                                        }
                                                    }
                                                }
                                            }
                                        }}})

            elif ci.check('FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON'):
                p = ci.by_path('FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON').get(
                    'PRECONDITIONER', Keyword('PRECONDITIONER', 'FULL_ALL')
                )

                if p == Keyword('PRECONDITIONER', 'FULL_SINGLE_INVERSE'):
                    actions.append({'dict': self.input_file,
                                    "action": {"_set": {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'SCF': {
                                                    'DIAGONALIZATION': {
                                                        'DAVIDSON': {
                                                            'PRECONDITIONER': 'FULL_ALL'
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }}})

                else:
                    p = ci.by_path('FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON').get(
                        'PRECOND_SOLVER', Keyword('PRECOND_SOLVER', 'DEFAULT')
                    )
                    if p.values[0] == 'DEFAULT':
                        actions.append({'dict': self.input_file,
                                        "action": {"_set": {
                                            'FORCE_EVAL': {
                                                'DFT': {
                                                    'SCF': {
                                                        'DIAGONALIZATION': {
                                                            'DAVIDSON': {
                                                                'PRECOND_SOLVER': 'DIRECT'
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }}})

            self.frozen_preconditioner = False
            errors.append('Frozen preconditioner')

        else:
            errors.append('Frozen job')

        restart(actions, self.output_file, self.input_file)
        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {"errors": errors, "actions": actions}


class AbortHandler(ErrorHandler):
    """
    These are errors that cp2k recognizes internally, and causes a kill-signal,
    as opposed to things like slow scf convergence, which is an unwanted feature of
    optimization rather than an error per se. Currently this error handler recognizes
    the following:

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
            output_file: (str) nam eof the output file
        """

        self.input_file = input_file
        self.output_file = output_file
        self.messages = {
            'cholesky': r'(Cholesky decomposition failed. Matrix ill conditioned ?)',
            'cholesky_scf': r'(Cholesky decompose failed: the matrix is not positive definite or)'
        }
        self.responses = []

    def check(self):
        matches = regrep(self.output_file, patterns=self.messages,
                         reverse=True, terminate_on_match=True,
                         postprocess=str)
        for m in matches:
            self.responses.append(m)
            return True
        return False

    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = []

        if self.responses[-1] == 'cholesky':
            n = self.responses.count('cholesky')
            if n == 1:
                # Change preconditioner
                p = ci['FORCE_EVAL']['DFT']['SCF']['OT'].get(
                    'PRECONDITIONER', Keyword('PRECONDITIONER', 'FULL_ALL')
                ).values[0]

                if p == 'FULL_ALL':
                    actions.append(
                        {
                            'dict': self.input_file,
                            "action": {
                                "_set": {
                                    'FORCE_EVAL': {
                                        'DFT': {
                                            'SCF': {
                                                'OT': {
                                                    'PRECONDITIONER': 'FULL_SINGLE_INVERSE'
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    )
                elif p == 'FULL_SINGLE_INVERSE':
                    actions.append(
                        {
                            'dict': self.input_file,
                            "action": {
                                "_set": {
                                    'FORCE_EVAL': {
                                        'DFT': {
                                            'SCF': {
                                                'OT': {
                                                    'PRECONDITIONER': 'FULL_ALL'
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    )

            if n == 2:
                # preconditioner was fine, make sure eps_default is at least 1e-12
                p = ci['force_eval']['dft']['qs'].get(
                    'EPS_DEFAULT',
                    Keyword('EPS_DEFAULT', 1e-12)
                ).values[0]
                if p > 1e-12:
                    actions.append({
                            "dict": self.input_file,
                            "action": {
                                "_set":
                                    {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'QS': {
                                                    'EPS_DEFAULT': 1e-12
                                                }
                                            }
                                        }
                                    }

                            }
                        }
                    )
                else:
                    n += 1

            if n == 3:
                # bump up overlap matrix resolution
                eps_default = ci['force_eval']['dft']['qs'].get(
                    'EPS_DEFAULT',
                    Keyword('EPS_DEFAULT', 1e-12)
                ).values[0]
                p = ci['force_eval']['dft']['qs'].get(
                    'EPS_PGF_ORB',
                    Keyword('EPS_PGF_ORB', np.sqrt(eps_default))
                ).values[0]
                actions.append({
                    "dict": self.input_file,
                    "action": {
                        "_set": {
                                'FORCE_EVAL': {
                                    'DFT': {
                                        'QS': {
                                            'EPS_PGF_ORB': 1e-10 if p > 1e-10 else p / 10
                                        }
                                    }
                                }
                            }

                    }
                }
                )

            if n == 4:
                # restart file could be problematic (gga restart for hybrids)
                if ci['force_eval']['dft'].get('wfn_restart_file_name'):
                    actions.append(
                        {
                            'dict': self.input_file,
                            'action': {
                                "_unset": {
                                    'FORCE_EVAL': {
                                        'DFT': 'WFN_RESTART_FILE_NAME'
                                    }
                                },
                                "_set": {
                                    'FORCE_EVAL': {
                                        'DFT': {
                                            'XC': {
                                                'HF': {
                                                    'SCREENING': {
                                                        'SCREEN_ON_INITIAL_P': False,
                                                        'SCREEN_P_FORCES': False
                                                    },
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    )

        elif self.responses[-1] == 'cholesky_scf':
            n = self.responses.count('cholesky_scf')
            if n == 1:
                p = ci['FORCE_EVAL']['DFT']['SCF'].get(
                    'CHOLESKY', Keyword('CHOLESKY', 'RESTORE')
                ).values[0]

                if p == 'RESTORE':
                    actions.append(
                        {
                            'dict': self.input_file,
                            "action": {
                                "_set": {
                                    'FORCE_EVAL': {
                                        'DFT': {
                                            'SCF': {
                                                'CHOLESKY': 'INVERSE'
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    )

        restart(actions, self.output_file, self.input_file)
        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {'errors': [self.responses[-1]], 'actions': actions}


class NumericalPrecisionHandler(ErrorHandler):

    """
    CP2K offers lots of functionality for decreasing numerical
    precision in order to speed-up calculations. This can, unfortunately,
    lead to convergence cycles getting 'stuck'. While it can be hard to
    separate numerical issues from things like optimizer choice, slow-to-converge
    systems, or divergence issues, this handler specifically detects the problem of
    convergence getting stuck, where the same convergence value is returned many times
    in a row. Numerical precision can also be the cause of oscillating convergence.
    This is a little harder to assess, as it can also just look like slow-convergence.
    Currently, we have identified the following causes of this problem:

        (1) EPS_DEFAULT: Sets the overall precision of the Quickstep module (note, not
            the same as EPS_SCF). The CP2K default of 1e-10 works fine for simple systems
            but will almost certainly fail for open-shell or defective systems. 1e-12 is
            recommended, with some applications needing 1e-14. The handler will reduce
            eps_default until 1e-16, at which point its probably something else causing the
            problem.

        (2) XC_GRID: The default xc grid is usually sufficient, but systems that have strong
            xc grid that is double precision.

        (3) HF Screening: The numerical approximations used to speed up hybrid calculations
            can lead to imprecision. EPS_SCHWARZ should be at least 1e-7, for example.

        (4) ADMM Basis: When using admm, the polarization term being neglected can sometimes
            lead to issues.
    """

    is_monitor = True

    def __init__(self, input_file="cp2k.inp", output_file="cp2k.out", max_same=3):
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
        """
        self.input_file = input_file
        self.output_file = output_file
        self.max_same = max_same
        self.overlap_condition = None

    def check(self):
        conv = get_conv(self.output_file)
        counts = [sum(1 for i in g) for k, g in itertools.groupby(conv)]
        if any([c > self.max_same for c in counts]):
            return True
        return False

    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = []

        if ci.check('FORCE_EVAL/DFT/XC/HF'):  # Hybrid has special considerations
            if ci.check('FORCE_EVAL/DFT/XC/HF/SCREENING'):
                eps_schwarz = ci.by_path('FORCE_EVAL/DFT/XC/HF/SCREENING').get(
                    'EPS_SCHWARZ', Keyword('EPS_SCHWARZ', 1e-10)).values[0]
                if eps_schwarz > 1e-7:
                    actions.append({'dict': self.input_file,
                                    "action": {"_set": {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'XC': {
                                                    'HF': {
                                                        'SCREENING': {
                                                            'EPS_SCHWARZ': 1e-7
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }}})
            for k, v in ci.by_path('FORCE_EVAL/SUBSYS').subsections.items():
                    if v.name.upper() == 'KIND':
                        el = v.get('ELEMENT').values or v.section_parameters
                        el = el[0]
                        bs = ci.by_path('FORCE_EVAL/SUBSYS')[k].get('BASIS_SET', None)
                        if isinstance(bs, Sequence):
                            for i in range(len(bs)):
                                if 'AUX_FIT' in [val.upper() for val in bs[i].values]:
                                    aux = None
                                    if el == 'Li':  # special case of Li aux basis
                                        aux = get_aux_basis({el: 'cFIT4-SR'})
                                    elif not bs[i].values[1].startswith('cp'):
                                        aux = get_aux_basis({el: None}, 'cpFIT')
                                        if not aux.get(el, '').startswith('cpFIT'):
                                            aux = None
                                    if aux:
                                        bs.keywords.pop(i)
                                        actions.append({'dict': self.input_file,
                                                        "action": {"_set": {
                                                            'FORCE_EVAL': {
                                                                'SUBSYS': {
                                                                    k: {
                                                                        'BASIS_SET': 'AUX_FIT '+aux[el]
                                                                    }
                                                                }
                                                            }
                                                    }}})
                                        for _bs in bs:
                                            actions.append({
                                                'dict': self.input_file,
                                                'action': {
                                                    "_inc": {
                                                        'FORCE_EVAL': {
                                                            'SUBSYS': {
                                                                k: {
                                                                    'BASIS_SET': ' '.join(_bs.values)
                                                                }}}}}})
                                        break

            m = regrep(
                self.output_file,
                patterns={
                    'PGF': re.compile(r'WARNING in hfx_energy_potential.F:592 :: The Kohn Sham matrix is not')}
                )
            eps_default = ci.by_path('FORCE_EVAL/DFT/QS').get('EPS_DEFAULT', Keyword('EPS_DEFAULT', 1e-10)).values[0]
            pgf = ci['force_eval']['dft']['qs'].get(
                'EPS_PGF_ORB', Keyword('EPS_PGF_ORB', np.sqrt(eps_default))
            ).values[0]
            if m.get('PGF'):
                actions.append({
                    'dict': self.input_file,
                    "action": {
                        "_set": {
                            'FORCE_EVAL': {
                                'DFT': {
                                    'QS': {
                                        'EPS_PGF_ORB': pgf / 10
                                    }
                                }
                            }
                        }}})

        # If no hybrid modifications were performed
        if len(actions) == 0:
            eps_default = ci.by_path('FORCE_EVAL/DFT/QS').get('EPS_DEFAULT', Keyword('EPS_DEFAULT', 1e-10)).values[0]

            # overlap matrix precision
            pgf = ci['force_eval']['dft']['qs'].get(
                'EPS_PGF_ORB', Keyword('EPS_PGF_ORB', np.sqrt(eps_default))
            ).values[0]

            # realspace KS matrix precision
            gvg = ci['force_eval']['dft']['qs'].get(
                'EPS_GVG_RSPACE', Keyword('EPS_GVG_RSPACE', np.sqrt(eps_default))
            ).values[0]

            if eps_default > 1e-12:
                actions.append({
                    'dict': self.input_file,
                    "action": {
                        "_set": {
                            'FORCE_EVAL': {
                                'DFT': {
                                    'QS': {
                                        'EPS_DEFAULT': 1e-12
                                    }
                                }
                            }
                        }}})

            elif 1e-12 >= eps_default > 1e-16:
                actions.append({
                    'dict': self.input_file,
                    "action": {
                        "_set": {
                            'FORCE_EVAL': {
                                'DFT': {
                                    'QS': {
                                        'EPS_DEFAULT': eps_default / 100
                                    }
                                }
                            }
                        }}})

            elif pgf > 1e-10 or gvg > 1e-10:
                if pgf > 1e-10:
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set":
                                    {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'QS': {
                                                    'EPS_PGF_ORB': 1e-10,
                                                }
                                            }
                                        }
                                    }

                            }
                        }
                    )
                if gvg > 1e-10:
                    actions.append(
                        {
                            "dict": self.input_file,
                            "action": {
                                "_set":
                                    {
                                        'FORCE_EVAL': {
                                            'DFT': {
                                                'QS': {
                                                    'EPS_GVG_RSPACE': 1e-10
                                                }
                                            }
                                        }
                                    }

                            }
                        }
                    )

            else:
                # Try a more expensive XC grid
                tmp = {'dict': self.input_file,
                        "action": {
                            "_set": {
                                'FORCE_EVAL': {
                                    'DFT': {
                                        'XC': {
                                            'XC_GRID': {
                                                'USE_FINER_GRID': True
                                            }
                                        }
                                    }
                                }
                        }}}
                if not ci.check('FORCE_EVAL/DFT/XC/XC_GRID'):
                    actions.append(tmp)
                elif ci.by_path('FORCE_EVAL/DFT/XC/XC_GRID').get('XC_GRID', None):
                    actions.append(tmp)

        restart(actions, self.output_file, self.input_file)
        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {"errors": ["Unsufficient precision"], "actions": actions}


class UnconvergedRelaxationErrorHandler(ErrorHandler):

    """
    This handler checks to see if geometry optimization has failed to converge,
    as signified by a line in the output file that says the maximum number of optimization
    steps were reached.

    At present, this handler does the following:

        (1) If the geometry optimization failed using the fast (L)BFGS, switch to the slower, but more
            robust CG algorithm with 2 point line search.
    """

    is_monitor = True

    def __init__(self, input_file='cp2k.inp', output_file='cp2k.out'):
        """
        Initialize the error handler.

        Args:
            input_file: name of the input file
            output_file: name of the output file
        """

        self.input_file = input_file
        self.output_file = output_file

    def check(self):
        o = Cp2kOutput(self.output_file)
        o.convergence()
        if o.data.get("geo_opt_not_converged"):
            return True
        return False

    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = list()

        if ci.check('MOTION/GEO_OPT'):
            if ci['motion']['geo_opt'].get(
                    'OPTIMIZER', Keyword('OPTIMIZER', 'BFGS')
            ).values[0].upper() == ('BFGS' or 'LBFGS'):
                max_iter = ci['motion']['geo_opt'].get('MAX_ITER', Keyword('', 200)).values[0]
                actions.append({
                    'dict': self.input_file,
                    "action": {
                        "_set": {
                            'MOTION': {
                                'GEO_OPT': {
                                    'OPTIMIZER': 'CG',
                                    'MAX_ITER': max_iter*2,
                                    'CG': {
                                        'LINE_SEARCH': {
                                            'TYPE': '2PNT'
                                        }
                                    }
                                }
                            }
                        }}})

        restart(actions, self.output_file, self.input_file)
        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {"errors": ["Unsuccessful relaxation"], "actions": actions}


class WalltimeHandler(ErrorHandler):

    """
    This walltime error handler, when enabled, will detect whether
    the CP2K internal walltime handler has been tripped. If walltime
    has been reached (plus some buffer), then the walltime handler will create a
    "checkpoint.json" file that enables the job to continue. This is
    different than saving successful runs as custodian.chk.#.tar.gz
    (see Custodian), and simply creates checkpoint.json
    """

    is_monitor = False
    raises_runtime_error = False
    is_terminating = False

    def __init__(self, output_file='cp2k.out', enable_checkpointing=True):
        """
        Initialize this handler.

        Args:
            output_file (str): name of the cp2k output file
            enable_checkpointing (bool): whether or not to enable checkpointing when
                the walltime is reached by dumping checkpoint.json
        """
        self.output_file = output_file
        self.enable_checkpointing = enable_checkpointing

    def check(self):
        if regrep(
                filename=self.output_file,
                patterns={"walltime": r"(exceeded requested execution time)"},
                reverse=True,
                terminate_on_match=True,
                postprocess=bool
        ).get("walltime"):
            return True
        return False

    def correct(self):
        if self.enable_checkpointing:
            dumpfn({"_path": os.getcwd()}, fn="checkpoint.json")
        return {"errors": ["Walltime error"], "actions": []}
