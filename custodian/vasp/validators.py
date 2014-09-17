# coding: utf-8

from __future__ import unicode_literals, division

from custodian.custodian import Validator
from pymatgen.io.vaspio.vasp_output import Vasprun


class VasprunXMLValidator(Validator):
    """
    Checks that a valid vasprun.xml was generated
    """

    def check(self):
        try:
            Vasprun("vasprun.xml")
        except:
            return True
        return False
