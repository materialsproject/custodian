""" This module implements specific error handler for Lobster runs. """

import os

from pymatgen.io.lobster import Lobsterout

from custodian.custodian import Validator

__author__ = "Janine George, Guido Petretto"
__copyright__ = "Copyright 2020, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Janine George"
__email__ = "janine.george@uclouvain.be"
__date__ = "April 27, 2020"


class EnoughBandsValidator(Validator):
    """
    validates if enough bands for COHP calculation are available
    """

    def __init__(self, output_filename: str = "lobsterout"):
        """

        Args:
            output_filename: filename of output file, usually lobsterout
        """
        self.output_filename = output_filename

    def check(self) -> bool:
        """
        checks if the VASP calculation had enough bands
        Returns:
            (bool) if True, too few bands have been applied
        """
        # checks if correct number of bands is available
        try:
            with open(self.output_filename) as f:
                data = f.read()
            return "You are employing too few bands in your PAW calculation." in data
        except OSError:
            return False


class LobsterFilesValidator(Validator):
    """
    Check for existence of some of the files that lobster
        normally create upon running.
    Check if lobster terminated normally by looking for finished
    """

    def __init__(self):
        """
        Dummy init
        """

    def check(self) -> bool:
        """
        Check for errors.
        """
        for vfile in ["lobsterout"]:
            if not os.path.exists(vfile):
                return True
        with open("lobsterout") as f:
            data = f.read()
        return "finished" not in data


class ChargeSpillingValidator(Validator):
    """
    Check if spilling is below certain threshold!
    """

    def __init__(self, output_filename: str = "lobsterout", charge_spilling_limit: float = 0.05):
        """

        Args:
            output_filename: filename of the output file of lobter, usually lobsterout
            charge_spilling_limit: limit of the charge spilling that will be considered okay
        """

        self.output_filename = output_filename
        self.charge_spilling_limit = charge_spilling_limit

    def check(self) -> bool:
        """open lobsterout and find charge spilling"""

        if os.path.exists(self.output_filename):
            lobsterout = Lobsterout(self.output_filename)
            if lobsterout.charge_spilling[0] > self.charge_spilling_limit:
                return True
            if len(lobsterout.charge_spilling) > 1:
                if lobsterout.charge_spilling[1] > self.charge_spilling_limit:
                    return True
            return False
        return False
