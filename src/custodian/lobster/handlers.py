"""This module implements specific error handler for Lobster runs."""

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
    """validates if enough bands for COHP calculation are available."""

    def __init__(self, output_filename: str = "lobsterout") -> None:
        """

        Args:
            output_filename: filename of output file, usually lobsterout.
        """
        self.output_filename = output_filename

    def check(self, directory: str = "./") -> bool:
        """
        Checks if the VASP calculation had enough bands
        Returns:
            (bool) if True, too few bands have been applied.
        """
        # checks if correct number of bands is available
        try:
            with open(os.path.join(directory, self.output_filename)) as file:
                data = file.read()
            return "You are employing too few bands in your PAW calculation." in data
        except OSError:
            return False


class LobsterFilesValidator(Validator):
    """
    Check for existence of some of the files that lobster
        normally create upon running.
    Check if lobster terminated normally by looking for finished.
    """

    def __init__(self) -> None:
        """Dummy init."""

    def check(self, directory: str = "./") -> bool:
        """Check for errors."""
        for filename in ("lobsterout",):
            if not os.path.isfile(os.path.join(directory, filename)):
                return True
        with open(os.path.join(directory, "lobsterout")) as file:
            data = file.read()
        return "finished" not in data


class ChargeSpillingValidator(Validator):
    """Check if spilling is below certain threshold!"""

    def __init__(self, output_filename: str = "lobsterout", charge_spilling_limit: float = 0.05) -> None:
        """

        Args:
            output_filename: filename of the output file of lobster, usually lobsterout
            charge_spilling_limit: limit of the charge spilling that will be considered okay.
        """
        self.output_filename = output_filename
        self.charge_spilling_limit = charge_spilling_limit

    def check(self, directory: str = "./") -> bool:
        """Open lobsterout and find charge spilling."""
        if os.path.isfile(os.path.join(directory, self.output_filename)):
            lobsterout = Lobsterout(os.path.join(directory, self.output_filename))
            if lobsterout.charge_spilling[0] > self.charge_spilling_limit:
                return True
            return bool(
                len(lobsterout.charge_spilling) > 1 and lobsterout.charge_spilling[1] > self.charge_spilling_limit
            )
        return False
