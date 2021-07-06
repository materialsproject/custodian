from abc import abstractmethod, abstractproperty

from custodian.custodian import Validator
from pymatgen.io.cp2k.outputs import Cp2kOutput


class Cp2kValidator(Validator):

    @abstractmethod
    def check(self):
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
        self.output_file = output_file
        self.completed = False
        self._check = False

    def check(self):
        try:
            o = Cp2kOutput(self.output_file)
            o.ran_successfully()
            if o.completed:
                return False
            else:
                self._check = True
                return True
        except:
            self._check = True
            return True
        
    @property
    def kill(self):
        """
        Raise this an error
        """
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
