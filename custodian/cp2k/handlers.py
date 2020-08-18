# coding: utf-8

from __future__ import unicode_literals, division

# This module implements new error handlers for QChem runs.

import os
import time
import numpy as np
from collections import Counter, deque
from pymatgen.io.cp2k.inputs import Cp2kInput
from pymatgen.io.cp2k.outputs import Cp2kOutput
from custodian.custodian import ErrorHandler
from custodian.utils import backup
from custodian.cp2k.interpreter import Cp2kModder

__author__ = "Nicholas Winner"
__version__ = "0.1"


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
    walltime handling can vibe done natively in CP2K, and will have added benefits like
    writing a wavefunction restart file before quiting. 
"""

CP2K_BACKUP_FILES = {"cp2k.out", "cp2k.inp", "std_err.txt"}


class StdErrHandler(ErrorHandler):
    """
    Master StdErr class that handles a number of common errors
    that occur during Cp2k runs with error messages only in
    the standard error.
    """

    is_monitor = True

    error_msgs = {
        "seg_fault": [""],
        "invalid_memory_reference": [""],
        "out_of_memory": [""],
        "ORTE": ["ORTE"]
    }

    def __init__(self, output_filename="std_err.txt"):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stderr for vasp
                is being redirected. The error messages that are checked are
                present in the stderr. Defaults to "std_err.txt", which is the
                default redirect used by :class:`custodian.vasp.jobs.Cp2kJob`.
        """
        self.output_filename = output_filename
        self.errors = set()
        self.error_count = Counter()

    def check(self):
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in StdErrHandler.error_msgs.items():
                    for msg in msgs:
                        if l.find(msg) != -1:
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        pass


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
        for ext in ["", ".gz", ".GZ", ".z", ".Z", ".bz2", ".BZ2"]:
            if os.path.exists(self.input_file + ext):
                ci = Cp2kInput.from_file(self.input_file + ext)
        if ci['GLOBAL']['RUN_TYPE'].values[0].upper() in [
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
            if ci['FORCE_EVAL']['DFT']['SCF']['OT']['MINIMIZER'].values[0].upper() == 'DIIS':
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
            elif ci['FORCE_EVAL']['DFT']['SCF']['OT']['MINIMIZER'].values[0].upper() == 'CG':
                if ci['FORCE_EVAL']['DFT']['SCF']['OT']['LINESEARCH'].values[0].upper() != '3PNT':
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
                elif ci['FORCE_EVAL']['DFT']['SCF']['OT']['MAX_SCF'].values[0] < 50:
                        actions.append({'dict': self.input_file,
                                        "action": {"_set": {
                                            'FORCE_EVAL': {
                                                'DFT': {
                                                    'SCF': {
                                                        'MAX_SCF': 50
                                                    }
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

        if actions:
            Cp2kModder(ci=ci).apply_actions(actions)

        return {"errors": ["Non-converging Job"], "actions": actions}


class OtEigen(ErrorHandler):

    is_monitor = True

    def __init__(self, output_filename="cp2k.out", input_filename="cp2k.inp"):

        self.output_filename = output_filename
        self.input_filename = input_filename


class FrozenJobErrorHandler(ErrorHandler):
    """
    Detects an error when the output file has not been updated
    in timeout seconds. The reason for this can be a slow step
    (i.e. HFX 4-electron integrals are very slow, and don't update
    the output until they are completed), or cp2k hanging.
    """

    is_monitor = True

    def __init__(self, output_filename="cp2k.out", timeout=3600):
        """
        Initializes the handler with the output file to check.

        Args:
            output_filename (str): This is the file where the stdout for vasp
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "vasp.out", which is the
                default redirect used by :class:`custodian.vasp.jobs.VaspJob`.
            timeout (int): The time in seconds between checks where if there
                is no activity on the output file, the run is considered
                frozen. Defaults to 3600 seconds, i.e., 1 hour.
        """
        self.output_filename = output_filename
        self.timeout = timeout

    def check(self):
        st = os.stat(self.output_filename)
        t = tail(self.output_filename, 10)
        t1, t2 = t[-1].split(), t[-2].split()

        # Quicker than waitin for long time-out threshold. If SCF step
        # Is taking more than 4 times the previous SCF step, then the
        # job is likely frozen
        if len(t1) > 1:
            if t1[1].__contains__('OT') or t1[1].__contains__('Diag'):
                if len(t2) > 1:
                    if t2[1].__contains__('OT') or t2[1].__contains__('Diag'):
                        if float(t1[3]) > 4*float(t2[3]):
                            return True
        if time.time() - st.st_mtime > self.timeout:
            return True
        return False

    def correct(self):
        backup(VASP_BACKUP_FILES | {self.output_filename})

        vi = VaspInput.from_directory('.')
        actions = []
        if vi["INCAR"].get("ALGO", "Normal") == "Fast":
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"ALGO": "Normal"}}})
        else:
            actions.append({"dict": "INCAR",
                            "action": {"_set": {"SYMPREC": 1e-8}}})

        VaspModder(vi=vi).apply_actions(actions)

        return {"errors": ["Frozen job"], "actions": actions}


def tail(filename, n=10):
    """
    Returns the last n lines of a file as a list (including empty lines)
    """
    return deque(open(filename), n)

