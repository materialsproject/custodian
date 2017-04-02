# coding: utf-8

from __future__ import unicode_literals, division

from custodian.custodian import Validator
from pymatgen.io.vasp import Vasprun, Incar, Outcar
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


class VaspNpTMDValidator(Validator):
    """
    Check NpT-AIMD settings is loaded by VASP compiled with -Dtbdyn.
    Currently, VASP only have Langevin thermostat (MDALGO = 3) for NpT ensemble.
    """

    def __init__(self):
        pass

    def check(self):
        incar = Incar.from_file("INCAR")
        is_npt = incar.get("MDALGO") == 3
        if not is_npt:
            return False

        outcar = Outcar("OUTCAR")
        patterns = {"MDALGO": "MDALGO\s+=\s+([\d]+)"}
        outcar.read_pattern(patterns=patterns)
        if outcar.data["MDALGO"] == [['3']]:
            return False
        else:
            return True
