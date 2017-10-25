# coding: utf-8

from __future__ import unicode_literals, division
from custodian.custodian import ErrorHandler
import re
from custodian.utils import backup
from pymatgen.io.feff.sets import FEFFDirectoryInput
from custodian.feff.interpreter import FeffModder
import numpy as np
import logging

FEFF_BACKUP_FILES = ["ATOMS", "HEADER", "PARAMETERS", "POTENTIALS", "feff.inp"]

logger = logging.getLogger(__name__)


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
            return self._notconverge_check()
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

        nmix_values = np.array([1, 3, 5, 10])

        if nscmt < 100:
            scf_values[2] = 100

        if ca < 0.1 and nmix < 10:
            scf_values[4] = nmix_values[np.argmax(nmix_values > nmix)]

        # When ca equals 0.1 and nmix equals 10, halve the ca value
        if ca <= 0.1 and nmix == 10 and ca >= 0.01:
            scf_values[3] = round(ca / 2, 2)
            scf_values[4] = 3

        if ca >= 0.1 and nmix < 10:
            scf_values[3] = 0.1
            scf_values[4] = nmix_values[np.argmax(nmix_values > nmix)]

        if scf_values_orig != scf_values:
            actions.append({"dict": "PARAMETERS",
                            "action": {"_set": {"SCF": scf_values}}})

        if actions:
            FeffModder().apply_actions(actions)
            return {"errors": ["Non-converging job"], "actions": actions}

        # Unfixable error. Just return None for actions.
        else:
            return {"errors": ["Non-converging job"], "actions": None}
