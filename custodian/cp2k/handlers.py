# coding: utf-8

from __future__ import unicode_literals, division

# This module implements new error handlers for QChem runs.

import os
from pymatgen.io.cp2k.inputs import Cp2kInput
from pymatgen.io.cp2k.outputs import Cp2kOuput
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

    def check(self):
        # Checks output file for errors.
        out = Cp2kOuput(self.output_file, auto_load=False, verbose=False)
        out._convergence()
        for scf_loop in out['scf_converged']:
            if not scf_loop[0]:
                return False
        return True

    def correct(self):
        ci = Cp2kInput.from_file(self.input_file)
        actions = []

        """
        Non-converging SCF can have two flavors:
        (1) OT Diagonalization:
            If OT is applicable, convergence is easier, if not convering, can try the following:
                (1) Increase number of outer loops and decrease number of inner loops
                (2) Increase both
                (3) Switch to CG minimization 
        (2) If normal Davidson minimization:
            Follow the VASP custodian charge mixing updates
        """
        if ci.check('FORCE_EVAL/DFT/SCF/OT'):
            if ci['FORCE_EVAL']['DFT']['SCF']['OT'].get_keyword('MINIMIZER').values == ['DIIS']:
                actions.append({'dict': self.input_file,
                                "action": {"_set": {'FORCE_EVAL': {'DFT': {'SCF': {'OT': {'MINIMIZER': 'CG'}}}}}}})
            elif ci['FORCE_EVAL']['DFT']['SCF']['OT'].get_keyword('MINIMIZER').values == ['CG']:
                actions.append({'dict': self.input_file,
                                "action": {"_set": {'FORCE_EVAL': {'DFT': {'SCF': {'OT': {'MINIMIZER': 'CG'}}}}}}})

        actions = [{'dict': "cp2k.inp", "action": {'_set': {'FORCE_EVAL': {'DFT': {'UKS': False}}}}}]

        if actions:
            Cp2kModder(ci=ci).apply_actions(actions)

        return {"errors": ["Non-converging Job"], "actions": actions}

