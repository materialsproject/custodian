# coding: utf-8

from __future__ import unicode_literals, division

from custodian.custodian import Validator
from pymatgen.io.vasp import Vasprun
import os

class VasprunXMLValidator(Validator):
    """
    Checks that a valid vasprun.xml was generated
    """

    def __init__(self):
        pass

    def check(self):
        try:
            Vasprun("vasprun.xml")
        except:
            return True
        return False


class VaspFilesValidator(Validator):
    """
    Check for existence of some of the files that VASP
        normally create upon running.
    """

    def __init__(self):
        pass

    def check(self):
        for vfile in ["CONTCAR", "OSZICAR", "OUTCAR"]:
            if not os.path.exists(vfile):
                return True
        return False
