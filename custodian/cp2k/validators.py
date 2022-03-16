"""
Validators for CP2K calculations.
"""

from abc import abstractmethod, abstractproperty

from custodian.custodian import Validator
from pymatgen.io.cp2k.outputs import Cp2kOutput

__author__ = "Nicholas Winner"
__version__ = "1.0"
__email__ = "nwinner@berkeley.edu"
__date__ = "March 2022"


class Cp2kValidator(Validator):
    """
    Base validator.
    """

    @abstractmethod
    def check(self):
        """
        Check whether validation failed. Here, True means
        validation failed.
        """
        pass

    @property
    @abstractmethod
    def kill(self):
        """
        Kill the job with raise error.
        """
        pass

    @property
    @abstractmethod
    def exit(self):
        """
        Don't raise error, but exit the job
        """
        pass

    @property
    @abstractmethod
    def no_children(self):
        """
        Job should not have children
        """
        pass


class Cp2kOutputValidator(Cp2kValidator):
    """
    Checks that a valid cp2k output file was generated
    """    

    def __init__(self, output_file='cp2k.out'):
        """
        Args:
            output_file (str): cp2k output file to analyze
        """
        self.output_file = output_file
        self._check = False

    def check(self):
        """
        Check for valid output. Checks that the end of the
        program was reached, and that convergence was
        achieved.
        """
        try:
            o = Cp2kOutput(self.output_file)
            o.ran_successfully()
            o.convergence()
            if not o.data.get("geo_opt_converged") and not o.data.get("geo_opt_not_converged"):
                geom = True
            elif o.data.get("geo_opt_converged")[-1]:
                geom = True
            else:
                geom = False
            if o.completed and o.data.get("scf_converged", [True])[-1] and geom:
                return False
            else:
                self._check = True
                return True
        except:
            raise
            self._check = True
            return True
        
    @property
    def kill(self):
        return True

    @property
    def exit(self):
        return True

    @property
    def no_children(self):
        return True


