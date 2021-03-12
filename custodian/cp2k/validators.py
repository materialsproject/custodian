from custodian.custodian import Validator
from pymatgen.io.cp2k.outputs import Cp2kOutput


class Cp2kOutputValidator(Validator):
    """
    Checks that a valid cp2k output file was generated
    """

    def __init__(self, output_file='cp2k.out'):
        self.output_file = output_file
        self.completed = False

    def check(self):
        try:
            o = Cp2kOutput(self.output_file)
            o.ran_successfully()
            if o.completed:
                return False
            else:
                return True
        except:
            return True
        return False
