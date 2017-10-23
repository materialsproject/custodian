# coding: utf-8

from __future__ import unicode_literals, division
from custodian.custodian import ErrorHandler
import re
from custodian.utils import backup
from pymatgen.io.feff.sets import FEFFDirectoryInput
from custodian.feff.interpreter import FeffModder
import numpy as np

FEFF_BACKUP_FILES = {"ATOMS", "HEADER", "PARAMETERS", "POTENTIALS"}


class UnconvergedErrorHandler(ErrorHandler):
    """
    Check if a run's SCF is converged. If not
    """

    is_monitor = False

    def __init__(self, output_filename='log1.dat'):
        """
        Initializes the handler with the output file to check
        Args:
            output_filename (str): Filename for the log1.dat file. log1.dat file
             contains the SCF calculation convergence information. Change this only
             if it is different from the default (unlikely).
        """
        self.output_filename = output_filename

    def check(self):
        """
        If the FEFF run does not converge, the check will return
        "TRUE"
        """
        try:
            self._notconverge_check()
        except:
            pass
        return False

    def _notconverge_check(self):

        # Process the output file and get converge information
        not_converge_pattern = re.compile("Convergence not reached.*")
        converge_pattern = re.compile('Convergence reached.*')
        for _, line in enumerate(open(self.output_filename)):
            if len(not_converge_pattern.findall(line)) > 0:
                return True

            elif len(converge_pattern.findall(line)) > 0:
                return False

    def correct(self):
        backup(FEFF_BACKUP_FILES)
        feff_input = FEFFDirectoryInput.from_directory(".")
        scf_values = feff_input['PARAMETERS'].get("SCF")
        scf_values_orig = scf_values[:]
        nscmt = scf_values[2]
        ca = scf_values[3]
        nmix = scf_values[4]
        actions = []

        nmix_values = [1, 3, 5, 10]

        if nscmt < 100:
            scf_values[2] = 100

        if ca >= 0.02:
            ca = round(ca / 2, 2)
            scf_values[3] = ca

        if ca <= 0.05 and nmix < 10:
            scf_values = nmix_values[np.argmax(np.array(nmix_values))]

        if scf_values_orig != scf_values:
            actions.append({"dict": "PARAMETERS",
                            "action": {"_set": {"SCF": scf_values}}})

        if actions:
            FeffModder().apply_actions(actions)
            return {"errors": ["Non-converging job"], "actions": actions}

        # Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Non-converging job"], "actions": None}
