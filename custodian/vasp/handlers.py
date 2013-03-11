#!/usr/bin/env python

"""
This module implements specific error handlers for VASP runs. These handlers
tries to detect common errors in vasp runs and attempt to fix them on the fly
by modifying the input files.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "2/4/13"

import os
import shutil
import logging
import tarfile
import glob

from custodian.custodian import ErrorHandler
from pymatgen.io.vaspio.vasp_input import Incar, Poscar, VaspInput
from pymatgen.transformations.standard_transformations import \
    PerturbStructureTransformation
from pymatgen.io.vaspio.vasp_output import Vasprun
from custodian.ansible.intepreter import Modder


class VaspErrorHandler(ErrorHandler):

    error_msgs = {
        "tet": ["Tetrahedron method fails for NKPT<4",
                "Fatal error detecting k-mesh",
                "Fatal error: unable to match k-point",
                "Routine TETIRR needs special values"],
        "inv_rot_mat": ["inverse of rotation matrix was not found (increase "
                        "SYMPREC)"],
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
        self.errors = set()
        with open(self.output_filename, "r") as f:
            for line in f:
                l = line.strip()
                for err, msgs in VaspErrorHandler.error_msgs.items():
                    for msg in msgs:
                        if l.startswith(msg):
                            self.errors.add(err)
        return len(self.errors) > 0

    def correct(self):
        backup()
        actions = []
        vi = VaspInput.from_directory(".")

        if "tet" in self.errors:
            actions.append({'dict': 'INCAR',
                            'action': {'_set': {'ISMEAR': 0}}})
        if "inv_rot_mat" in self.errors:
            actions.append({'dict': 'INCAR',
                            'action': {'_set': {'SYMPREC': 1e-8}}})
        if "brmix" in self.errors:
            actions.append({'dict': 'INCAR',
                            'action': {'_set': {'IMIX': 1}}})
        if "subspacematrix" in self.errors:
            actions.append({'dict': 'INCAR',
                            'action': {'_set': {'INCAR->LREAL': False}}})
        if "tetirr" in self.errors or "incorrect_shift" in self.errors:
            actions.append({'dict': 'KPOINTS',
                            'action': {'_set': {'style': "Gamma"}}})
        if "mesh_symmetry" in self.errors:
            m = max(vi["KPOINTS"].kpts[0])
            actions.append({'dict': 'KPOINTS',
                            'action': {'_set': {'kpoints': [[m] * 3]}}})
        m = Modder()
        for a in actions:
            vi[a["dict"]] = m.modify_object(a["action"], vi[a["dict"]])
        vi["INCAR"].write_file("INCAR")
        vi["POSCAR"].write_file("POSCAR")
        vi["KPOINTS"].write_file("KPOINTS")
        return {"errors": list(self.errors), "actions": actions}

    def __str__(self):
        return "Vasp error"


class UnconvergedErrorHandler(ErrorHandler):
    #todo: Make this work using ansible.

    def check(self):
        try:
            v = Vasprun('vasprun.xml')
            if not v.converged:
                return True
        except:
            return False
        return False

    def correct(self):
        backup()
        shutil.copy("CONTCAR", "POSCAR")
        incar = Incar.from_file("INCAR")
        incar['ISTART'] = 1
        incar.write_file("INCAR")
        return {"errors": ["Unconverged"], "actions": "Restart from CONTCAR"}

    def __str__(self):
        return "Run unconverged."


class PoscarErrorHandler(ErrorHandler):

    def check(self):
        with open("vasp.out", "r") as f:
            output = f.read()
            for line in output.split("\n"):
                l = line.strip()
                if l.startswith("Found some non-integer element in rotation "
                                "matrix"):
                    return True
        return False

    def correct(self):
        #TODO: Add transformation applied to transformation.json if exists.
        backup()
        shutil.copy("POSCAR", "POSCAR.orig")
        p = Poscar.from_file("POSCAR")
        s = p.struct
        trans = PerturbStructureTransformation(0.05)
        new_s = trans.apply_transformation(s)
        p = Poscar(new_s)
        p.write_file("POSCAR")
        return {"errors": ["Rotation matrix"],
                "actions": "Peturb POSCAR and restart."}


def backup():
    error_num = 0
    for f in glob.glob("error.*.tar.gz"):
        toks = f.split(".")
        error_num = max(error_num, int(toks[1]))
    filename = "error.{}.tar.gz".format(error_num + 1)
    logging.info("Backing up run to {}.".format(filename))
    tar = tarfile.open(filename, "w:gz")
    for f in os.listdir("."):
        if not (f.startswith("error") and f.endswith(".tar.gz")):
            tar.add(f)
    tar.close()
