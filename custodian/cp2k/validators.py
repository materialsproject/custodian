"""
Validators for CP2K calculations.
"""

from abc import abstractmethod, abstractproperty

from custodian.custodian import Validator
from pymatgen.io.cp2k.outputs import Cp2kOutput

__author__ = "Nicholas Winner"
__version__ = "0.9"
__email__ = "nwinner@berkeley.edu"
__date__ = "October 2021"


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


class ChargedDefectValidator(Cp2kValidator):

    """
    If a output file is charged and no band gap exists, then the
    calculation is ill-posed. Meant to be used with a double job
    with the first being a safety check job.
    """

    def __init__(self, output_file='cp2k.out'):
        self.output_file = output_file
        self.charge = None
        self._check = False

    def check(self):
        o = Cp2kOutput(self.output_file)
        o.parse_initial_structure()
        o.parse_dos()
        self.charge = o.initial_structure.charge
        if o.band_gap or self.charge == 0:
            return False
        self._check = True
        return True
    
    @property
    def kill(self):
        """
        Do not kill the job with raise error.
        """
        return False
    
    @property
    def exit(self):
        """
        Don't raise error, but exit the job
        """
        return True if self.charge else False

    @property
    def no_children(self):
        return True


class HybridValidator(Cp2kValidator):

    def __init__(self, output_file='cp2k.out'):
        self.output_file = output_file
        self.charge = None
        self._check = False

    def check(self):
        o = Cp2kOutput(self.output_file)
        o.parse_initial_structure()
        o.parse_dos()
        self.charge = o.initial_structure.charge
        if o.band_gap is not None and o.band_gap:
            return False
        self._check = True
        return True

    @property
    def kill(self):
        """
        Do not kill the job with raise error.
        """
        return False

    @property
    def exit(self):
        """
        Don't raise error, but exit the job
        """
        return True if self.charge else False

    @property
    def no_children(self):
        """
        No children
        """
        return True
