#!/usr/bin/env python

"""
Created on Jun 1, 2012
"""

from __future__ import division

__author__ = "Shyue Ping Ong, Stephen Dacek"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import unittest
import os
import glob
import shutil
import datetime

from custodian.vasp.handlers import VaspErrorHandler, \
    UnconvergedErrorHandler, MeshSymmetryErrorHandler, WalltimeHandler, \
    MaxForceErrorHandler
from pymatgen.io.vaspio import Incar, Poscar


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')

cwd = os.getcwd()


def clean_dir():
    for f in glob.glob("error.*.tar.gz"):
        os.remove(f)
    for f in glob.glob("custodian.chk.*.tar.gz"):
        os.remove(f)


class VaspErrorHandlerTest(unittest.TestCase):

    def setUp(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("KPOINTS", "KPOINTS.orig")
        shutil.copy("POSCAR", "POSCAR.orig")
        shutil.copy("CHGCAR", "CHGCAR.orig")

    def test_check_correct(self):
        h = VaspErrorHandler("vasp.teterror")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['tet'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'ISMEAR': 0}},
                           'dict': 'INCAR'}])
        h = VaspErrorHandler("vasp.sgrcon")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['rot_matrix'])
        self.assertEqual(set([a["dict"] for a in d["actions"]]),
                         {"KPOINTS"})

        h = VaspErrorHandler("vasp.real_optlay")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['real_optlay'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'LREAL': False}},
                           'dict': 'INCAR'}])

    def test_aliasing(self):
        os.chdir(os.path.join(test_dir, "aliasing"))
        shutil.copy("INCAR", "INCAR.orig")
        h = VaspErrorHandler("vasp.aliasing")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['aliasing'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'NGX': 34}},
                           'dict': 'INCAR'}])

        clean_dir()
        shutil.move("INCAR.orig", "INCAR")
        os.chdir(test_dir)

    def test_mesh_symmetry(self):
        h = MeshSymmetryErrorHandler("vasp.ibzkpt")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['mesh_symmetry'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'kpoints': [[4, 4, 4]]}},
                           'dict': 'KPOINTS'}])

    def test_dentet(self):
        h = VaspErrorHandler("vasp.dentet")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['dentet'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'ISMEAR': 0}},
                           'dict': 'INCAR'}])

    def test_brmix(self):
        h = VaspErrorHandler("vasp.brmix")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ['brmix'])
        self.assertFalse(os.path.exists("CHGCAR"))

        shutil.copy("INCAR.nelect", "INCAR")
        h = VaspErrorHandler("vasp.brmix")
        self.assertEqual(h.check(), False)
        d = h.correct()
        self.assertEqual(d["errors"], [])

    def test_too_few_bands(self):
        os.chdir(os.path.join(test_dir, "too_few_bands"))
        shutil.copy("INCAR", "INCAR.orig")
        h = VaspErrorHandler("vasp.too_few_bands")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['too_few_bands'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'NBANDS': 501}},
                           'dict': 'INCAR'}])
        clean_dir()
        shutil.move("INCAR.orig", "INCAR")
        os.chdir(test_dir)

    def test_rot_matrix(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        subdir = os.path.join(test_dir, "poscar_error")
        os.chdir(subdir)
        shutil.copy("KPOINTS", "KPOINTS.orig")
        h = VaspErrorHandler()
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["rot_matrix"])
        os.remove(os.path.join(subdir, "error.1.tar.gz"))
        shutil.copy("KPOINTS.orig", "KPOINTS")
        os.remove("KPOINTS.orig")

    def test_to_from_dict(self):
        h = VaspErrorHandler("random_name")
        h2 = VaspErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), type(h))
        self.assertEqual(h2.output_filename, "random_name")

    def tearDown(self):
        os.chdir(test_dir)
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("CHGCAR.orig", "CHGCAR")
        clean_dir()
        os.chdir(cwd)


class UnconvergedErrorHandlerTest(unittest.TestCase):

    def setUp(cls):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)

    def test_check_correct(self):
        subdir = os.path.join(test_dir, "unconverged")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("KPOINTS", "KPOINTS.orig")
        shutil.copy("POSCAR", "POSCAR.orig")
        shutil.copy("CONTCAR", "CONTCAR.orig")

        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ['Unconverged'])

        os.remove(os.path.join(subdir, "error.1.tar.gz"))

        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("CONTCAR.orig", "CONTCAR")

    def test_to_from_dict(self):
        h = UnconvergedErrorHandler("random_name.xml")
        h2 = UnconvergedErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), UnconvergedErrorHandler)
        self.assertEqual(h2.output_filename, "random_name.xml")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)

class MaxForceErrorHandlerTest(unittest.TestCase):

    def setUp(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)

    def test_check_correct(self):
        #NOTE: the vasprun here has had projected and partial eigenvalues removed
        subdir = os.path.join(test_dir, "max_force")
        os.chdir(subdir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("POSCAR", "POSCAR.orig")

        h = MaxForceErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ['MaxForce'])

        os.remove(os.path.join(subdir, "error.1.tar.gz"))
        
        incar = Incar.from_file('INCAR')
        poscar = Poscar.from_file('POSCAR')
        contcar = Poscar.from_file('CONTCAR')
        
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("POSCAR.orig", "POSCAR")
        
        self.assertEqual(poscar.structure, contcar.structure)
        self.assertAlmostEqual(incar['EDIFF'], 0.00075)

    def tearDown(self):
        os.chdir(cwd)


class WalltimeHandlerTest(unittest.TestCase):

    def setUp(self):
        os.chdir(test_dir)

    def test_check_and_correct(self):
        # The test OSZICAR file has 60 ionic steps. Let's try a 1 hr wall
        # time with a 1min buffer
        h = WalltimeHandler(wall_time=3600, buffer_time=120)
        self.assertFalse(h.check())

        # This makes sure the check returns True when the time left is less
        # than the buffer time.
        h.start_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        self.assertTrue(h.check())

        # This makes sure the check returns True when the time left is less
        # than 3 x the average time per ionic step. We have a 62 min wall
        # time, a very short buffer time, but the start time was 62 mins ago
        h = WalltimeHandler(wall_time=3720, buffer_time=10)
        h.start_time = datetime.datetime.now() - datetime.timedelta(minutes=62)
        self.assertTrue(h.check())

        # Test that the STOPCAR is written correctly.
        h.correct()
        with open("STOPCAR") as f:
            content = f.read()
            self.assertEqual(content, "LSTOP = .TRUE.")
        os.remove("STOPCAR")

        h = WalltimeHandler(wall_time=3600, buffer_time=120,
                            electronic_step_stop=True)

        self.assertFalse(h.check())
        h.start_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        self.assertTrue(h.check())

        h.correct()
        with open("STOPCAR") as f:
            content = f.read()
            self.assertEqual(content, "LABORT = .TRUE.")
        os.remove("STOPCAR")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
