# coding: utf-8

from __future__ import unicode_literals, division

from custodian.custodian import Validator
from pymatgen.io.vasp import Vasprun, Incar, Outcar, Chgcar
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

class VaspAECCARValidator(Validator):
    """
    Check if the data in the AECCAR is corrupted
    """

    def __init__(self):
        pass

    def check(self):
        aeccar0 = Chgcar.from_file("AECCAR0")
        aeccar2 = Chgcar.from_file("AECCAR2")
        aeccar = aeccar0 + aeccar2
        return check_broken_chgcar(aeccar)

def check_broken_chgcar(chgcar):
    chgcar_data = chgcar.data['total']
    if (chgcar_data < 0).sum() > 100:
        # a decent bunch of the values are negative
        return True

    diff = chgcar_data[:-1, :-1, :-1] - chgcar_data[1:, 1:, 1:]
    if diff.max()/(chgcar_data.max() - chgcar_data.min()) > 0.95:
        # Some single diagonal finite difference is more than 95% of the entire range
        return True

    return False
