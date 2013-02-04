#!/usr/bin/env python

"""
TODO: Change the module doc.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "2/4/13"


import shutil

from custodian.handlers import ErrorHandler
from pymatgen.io.vaspio.vasp_input import Incar, Kpoints, Poscar
from pymatgen.io.vaspio.vasp_output import Vasprun


class IncarErrorHandler(ErrorHandler):

    def check(self):
        with open("vasp.out", "r") as f:
            output = f.read()
            for line in output.split("\n"):
                l = line.strip()
                if l.startswith("Tetrahedron method fails for NKPT<4") or l.strip().startswith("Fatal error detecting k-mesh") or l.strip().startswith("Fatal error: unable to match k-point"):
                    self.error = "tet"
                    return True
                elif l.startswith("inverse of rotation matrix was not found (increase SYMPREC)"):
                    self.error = "inv_rot_mat"
                    return True
                elif l.startswith("BRMIX: very serious problems"):
                    self.error = "brmix"
                    return True
                elif l.startswith("WARNING: Sub-Space-Matrix is not hermitian in DAV"):
                    self.error = "subspacematrix"
                    return True
        return False

    def correct(self):
        shutil.copy("INCAR", "INCAR.orig")
        incar = Incar.from_file("INCAR")
        if self.error == "tet":
            incar['ISMEAR'] = 0
        elif self.error == "inv_rot_mat":
            incar['SYMPREC'] = 1e-8
        elif self.error == "brmix":
            incar['IMIX'] = 1
        elif self.error == "subspacematrix":
            incar['LREAL'] = False
        incar.write_file("INCAR")

    def __str__(self):
        return "INCAR error"


class KpointsErrorHandler(ErrorHandler):

    def check(self):
        with open("vasp.out", "r") as f:
            output = f.read()
            for line in output.split("\n"):
                l = line.strip()
                if l.startswith("Routine TETIRR needs special values"):
                    self.error = "tetirr"
                    return True
                elif l.startswith("Could not get correct shifts"):
                    self.error = "incorrect_shift"
                    return True
        return False

    def correct(self):
        shutil.copy("KPOINTS", "KPOINTS.orig")
        kpoints = Kpoints.from_file("KPOINTS")
        if self.error == "tetirr":
            kpoints.style = "Gamma"
        elif self.error == "incorrect_shift":
            kpoints.style = "Gamma"
        kpoints.write_file("KPOINTS")

    def __str__(self):
        return "KPOINTS error"


class UnconvergedErrorHandler(ErrorHandler):

    def check(self):
        v = Vasprun('vasprun.xml')
        if not v.converged:
            return True
        return False

    def correct(self):
        shutil.copy("CONTCAR", "POSCAR")
        incar = Incar.from_file("INCAR")
        incar['ISTART'] = 1
        incar.write_file("INCAR")

    def __str__(self):
        return "Run unconverged."


class PoscarErrorHandler(ErrorHandler):

    def check(self):
        with open("vasp.out", "r") as f:
            output = f.read()
            for line in output.split("\n"):
                l = line.strip()
                if l.startswith("Found some non-integer element in rotation matrix"):
                    return True
        return False

    def correct(self):
        #TODO: Add transformation applied to transformation.json if exists.
        from pymatgen.transformations.standard_transformations import PerturbStructureTransformation
        shutil.copy("POSCAR", "POSCAR.orig")
        p = Poscar.from_file("POSCAR")
        s = p.struct
        trans = PerturbStructureTransformation(0.05)
        new_s = trans.apply_transformation(s)
        p = Poscar(new_s)
        p.write_file("POSCAR")


"""
Aflow Error 5 (classrotmat)

grep : "Reciprocal lattice and k-lattice belong"
fix : SYMPREC = 1E-10, KPOINTS (equilize mesh)

Aflow Error 9 (davidson)

grep : "WARNING: Sub-Space-Matrix is not hermitian in DAV"
fix : INCAR -> remove ALGO, IMIX, set ALGO=VERY_FAST

Aflow Error 10 (nbands)

grep : "BRMIX: very serious problems"
fix :
notes:
aflow tries to get NBANDS from the OUTCAR
-> nbands=atoi(word.substr(word.find("NBANDS")+7).c_str());
aflow then tries to get NBANDS from INCAR
Then it increases NBANDS via
nbands=nbands+5+nbands/5

"""
