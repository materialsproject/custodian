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
from collections import deque
import itertools
from pymatgen.io.cp2k.inputs import Cp2kInput, Keyword
from pymatgen.io.cp2k.outputs import Cp2kOutput
from pymatgen.io.cp2k.utils import get_aux_basis
from custodian.custodian import ErrorHandler
from custodian.cp2k.interpreter import Cp2kModder
from monty.re import regrep
from monty.os.path import zpath

__author__ = "Nicholas Winner"
__version__ = "0.3"
__email__ = "nwinner@berkeley.edu"
__date__ = "December 2020"


CP2K_BACKUP_FILES = {"cp2k.out", "cp2k.inp", "std_err.txt"}


class StdErrHandler(ErrorHandler):
    """
    Master StdErr class that handles a number of common errors
    that occur during Cp2k runs with error messages only in
    the standard error.

    These issues are generally not cp2k-specific, and have to do
    with hardware/slurm/memory/etc.
    """

    is_monitor = True

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
            output_filename (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.vasp.jobs.Cp2kJob`.
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
        self.mixing_hierarchy = ['BROYDEN_MIXING', 'PULAY', 'PULAY_LINEAR']
        if os.path.exists(zpath(self.input_file)):
                ci = Cp2kInput.from_file(zpath(self.input_file))
        if ci['GLOBAL']['RUN_TYPE'].values[0].__str__().upper() in [
            "ENERGY", "ENERGY_FORCE", "WAVEFUNCTION_OPTIMIZATION", "WFN_OPT"]:
            self.is_static = True
        else:
            self.is_static = False
        self.is_ot = True if ci.check('FORCE_EVAL/DFT/SCF/OT') else False
        if ci.check('FORCE_EVAL/DFT/SCF/MIXING/METHOD'):
            self.mixing_hierarchy = [m for m in self.mixing_hierarchy if m.upper() !=
                                     ci['FORCE_EVAL']['DFT']['SCF']['MIXING']['METHOD']]

    def check(self):
        # Checks output file for errors.
        out = Cp2kOutput(self.output_file, auto_load=False, verbose=False)
        out.convergence()

        # General catch for SCF not converged
        # If not static, mark not-converged if last 5 SCF loops
        # failed to converge
        scf = out.data['scf_converged'] or [True]
        if self.is_static:
            if not scf[0]:
                return True
        else:
            if not all(scf[-5:]):
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
                                                "MIXING": {}
                                            }
                                        }
                                    }
                                }}})
            if not ci.check('FORCE_EVAL/DFT/SCF/SMEARING'):
                actions.append({'dict': self.input_file,
                                'action': {"_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {
                                                "SMEARING": {
                                                    "ELEC_TEMP": 300,
                                                    "METHOD": "FERMI_DIRAC"
                                                }
                                            }
                                        }
                                    }
                                }}})

            _next = self.mixing_hierarchy.pop(0) if self.mixing_hierarchy else None
            if _next == 'BROYDEN_MIXING':
                actions.append({'dict': self.input_file,
                                'action': {"_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {
                                                "MIXING": {
                                                    "METHOD": "BROYDEN_MIXING",
                                                    "NBUFFER": 5,
                                                    "ALPHA": 0.2
                                                }
                                            }
                                        }
                                    }
                                }}})
            elif _next == 'PULAY':
                actions.append({'dict': self.input_file,
                                'action': {"_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {
                                                "MIXING": {
                                                    "METHOD": "PULAY",
                                                    "NBUFFER": 5,
                                                    "ALPHA": 0.2
                                                }
                                            }
                                        }
                                    }
                                }}})
            elif _next == 'PULAY_LINEAR':
                actions.append({'dict': self.input_file,
                                'action': {"_set": {
                                    "FORCE_EVAL": {
                                        "DFT": {
                                            "SCF": {
                                                "MIXING": {
                                                    "METHOD": "PULAY",
                                                    "NBUFFER": 5,
                                                    "ALPHA": 0.1,
                                                    "BETA": 0.01
                                                }
                                            }
                                        }
                                    }
                                }}})

        # If corrections were applied, AND convergence is already good (1e-5)
        # then discard the RESTART file if present
        if actions:
            if ci.check('force_eval/dft') and \
                    ci['force_eval']['dft'].get('wfn_restart_file_name'):
                conv = get_conv(self.output_file)
                if conv[-1] <= 1e-5:
                    actions.append(
                        {'dict': self.input_file,
                         'action':
                             {'_unset':
                                  {'FORCE_EVAL':
                                       {'DFT': {'WFN_RESTART_FILE_NAME'}}}}}
                    )
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
        if len(conv) > 10 and np.mean(np.diff(conv[-10:])) > 0:
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
                                            'EPS_DEFAULT': p / 10
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
                frozen. Defaults to 3600 seconds, i.e., 1 hour.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.timeout = timeout
        self.frozen_preconditioner = False
        self.frozen_scf = False

    def check(self):
        st = os.stat(self.output_file)

        out = Cp2kOutput(self.output_file, auto_load=False, verbose=False)
        out.parse_scf_opt()
        conv = out.data['scf_time']
        if conv:
            if len(conv[-1]) > 2:  # At least one precond and regular step
                if time.time() - st.st_mtime > 4*conv[-1][-1]:
                    self.frozen_scf = True
                    return True

        t = tail(self.output_file, 2)
        if t[0].split() == ['Step', 'Update', 'method', 'Time', 'Convergence', 'Total', 'energy', 'Change']:
            if time.time() - st.st_mtime > self.timeout:
                self.frozen_preconditioner = True
                return True

        if time.time() - st.st_mtime > self.timeout:
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

            self.frozen_preconditioner = False
            errors.append('Frozen preconditioner')

        elif self.frozen_scf:
            self.frozen_scf = False
            errors.append('Frozen scf')

        else:
            errors.append('Frozen job')

        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {"errors": errors, "actions": actions}


class AbortHandler(ErrorHandler):
    """
    These are errors that cp2k recognizes internally, and causes a kill-signal,
    as opposed to things like slow scf convergence, which is an unwanted feature of
    optimization rather than an error per se. Currently this error handler recognizes
    the following:

        (1) Cholesky decomposition error. Which can be caused by imprecision or a bad
            preconditioner.
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
            'cholesky': r'(Cholesky decomposition failed. Matrix ill conditioned ?)'
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
                                                    'PRECONDITIONEER': 'FULL_SINGLE_INVERSE'
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
                                                    'PRECONDITIONEER': 'FULL_ALL'
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
                p = ci['force_eval']['dft']['qs'].get(
                    'EPS_PGF_ORB',
                    Keyword('EPS_PGF_ORB', 1e-6)
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
                                "set": {
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
    in a row. Currently, we have identified the following causes of this problem:

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
                checks for consequetive convergence values, so if you have:

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
                if ci.by_path('FORCE_EVAL/DFT/XC/HF/SCREENING').get(
                        'EPS_SCHWARZ', Keyword('EPS_SCHWARZ', 1e-10)).values[0] > 1e-7:
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
                        el = v.section_parameters or v.get('ELEMENT').values
                        el = el[0]
                        bs = ci.by_path('FORCE_EVAL/SUBSYS')[k].get('BASIS_SET', None)
                        if isinstance(bs, Sequence):
                            for i in range(len(bs)):
                                if 'AUX_FIT' in [val.upper() for val in bs[i].values]:
                                    if not bs[i].values[1].startswith('cp'):
                                        aux = get_aux_basis({el: None}, 'cpFIT')
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

        # If no hybrid modifications were performed
        if len(actions) == 0:
            eps_default = ci.by_path('FORCE_EVAL/DFT/QS').get('EPS_DEFAULT', Keyword('EPS_DEFAULT', 1e-10)).values[0]

            if 1e-10 <= eps_default < 1e-16:
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
            else:
                # Try a more expensive XC grid
                actions.append({
                    'dict': self.input_file,
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
                        }}})

        Cp2kModder(ci=ci, filename=self.input_file).apply_actions(actions)
        return {"errors": ["Unsufficient precision"], "actions": actions}


def tail(filename, n=10):
    """
    Returns the last n lines of a file as a list (including empty lines)
    """
    with open(filename) as f:
        t = deque(f, n)
        if t:
            return t
        else:
            return ['']*n


def get_conv(outfile):
    """
    Helper function to get the convergence info from SCF loops

    Args:
        outfile (str): output file to parse
    Returns:
        returns convergence info (change in energy between SCF steps) as a
        single list (flattened across outer scf loops).
    """
    out = Cp2kOutput(outfile, auto_load=False, verbose=False)
    out.parse_scf_opt()
    return list(itertools.chain.from_iterable(out.data['convergence']))

