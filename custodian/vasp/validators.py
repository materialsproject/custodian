from custodian.custodian import Validator
from pymatgen.io.vaspio.vasp_output import Vasprun

import glob

class VasprunXMLValidator(Validator):
    """
    Checks that a valid vasprun.xml was generated
    """

    def check(self):
        try:
            fs = glob.glob("vasprun.xml*")
            f = sorted(fs, reverse=True)[0] if fs else None
            Vasprun(f)
        except:
            return True
        return False

    def __str__(self):
        return "VasprunXMLValidator"
