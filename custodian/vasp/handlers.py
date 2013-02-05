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
from pymatgen.io.vaspio.vasp_input import Incar, Poscar, VaspInput
from pymatgen.io.vaspio.vasp_output import Vasprun
from custodian.ansible.intepreter import Modder


class VaspErrorHandler(ErrorHandler):

    error_msgs = {
        "tet": ["Tetrahedron method fails for NKPT<4",
                "Fatal error detecting k-mesh",
                "Fatal error: unable to match k-point",
                "Routine TETIRR needs special values"],
        "inv_rot_mat": ["inverse of rotation matrix was not found (increase SYMPREC)"],
        "brmix": ["BRMIX: very serious problems"],
        "subspacematrix": ["WARNING: Sub-Space-Matrix is not hermitian in DAV"],
        "tetirr": ["Routine TETIRR needs special values"],
        "incorrect_shift": ["Could not get correct shifts"],
        "mesh_symmetry": ["Reciprocal lattice and k-lattice belong to "
                          "different class of lattices."]
    }

    def __init__(self, output_filename="vasp.out"):
        self.output_filename = output_filename

    def check(self):
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in VaspErrorHandler.error_msgs.items():
                    for msg in msgs:
                        if l.startswith(msg):
                            self.error = err
                            return True
        return False

    def correct(self):
        actions = []
        vi = VaspInput.from_directory(".")
        if self.error == "tet":
            actions.append({'_set': {'INCAR->ISMEAR': 0}})
        elif self.error == "inv_rot_mat":
            actions.append({'_set': {'INCAR->SYMPREC': 1e-8}})
        elif self.error == "brmix":
            actions.append({'_set': {'INCAR->IMIX': 1}})
        elif self.error == "subspacematrix":
            actions.append({'_set': {'INCAR->LREAL': False}})
        elif self.error == "tetirr":
            actions.append({'_set': {'KPOINTS->style': "Gamma"}})
        elif self.error == "incorrect_shift":
            actions.append({'_set': {'KPOINTS->style': "Gamma"}})
        elif self.error == "mesh_symmetry":
            m = max(vi["KPOINTS"].kpts[0])
            actions.append({'_set': {'KPOINTS->kpoints': [[m] * 3]}})
        m = Modder()
        for a in actions:
            vi = m.modify_object(a, vi)
        self.actions = actions
        vi.write_input(".")

    def __str__(self):
        return "Vasp error"


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
