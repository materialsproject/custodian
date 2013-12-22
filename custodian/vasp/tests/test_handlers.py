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

from custodian.vasp.handlers import VaspErrorHandler, \
    UnconvergedErrorHandler, MeshSymmetryErrorHandler, PBSWalltimeHandler


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')

cwd = os.getcwd()


def clean_dir():
    for f in glob.glob("error.*.tar.gz"):
        os.remove(f)
    for f in glob.glob("custodian.chk.*.tar.gz"):
        os.remove(f)


class VaspErrorHandlerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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
        h = VaspErrorHandler("vasp.classrotmat")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['rot_matrix'])
        self.assertEqual(set([a["dict"] for a in d["actions"]]),
                         {"POSCAR", "INCAR"})

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
        h = MeshSymmetryErrorHandler("vasp.classrotmat")
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
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['brmix'])
        self.assertFalse(os.path.exists("CHGCAR"))

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
        shutil.copy("POSCAR", "POSCAR.orig")
        h = VaspErrorHandler()
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["rot_matrix"])
        os.remove(os.path.join(subdir, "error.1.tar.gz"))
        shutil.copy("POSCAR.orig", "POSCAR")
        os.remove("POSCAR.orig")

    def test_to_from_dict(self):
        h = VaspErrorHandler("random_name")
        h2 = VaspErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), type(h))
        self.assertEqual(h2.output_filename, "random_name")

    @classmethod
    def tearDownClass(cls):
        os.chdir(test_dir)
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("CHGCAR.orig", "CHGCAR")
        clean_dir()
        os.chdir(cwd)


class UnconvergedErrorHandlerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)

    def test_check_correct(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        subdir = os.path.join(test_dir, "unconverged")
        os.chdir(subdir)
        # h = UnconvergedErrorHandler("POTCAR")
        # h.check()
        # d = h.correct()
        # self.assertEqual(d["errors"], ['Unconverged'])
        # self.assertEqual(d["actions"],
        #                  [{'file': 'CONTCAR',
        #                    'action': {'_file_copy': {'dest': 'POSCAR'}}},
        #                   {'dict': 'INCAR',
        #                    'action': {'_set': {"ISTART": 1, "ALGO": "Normal",
        #                                        "NELMDL": 6, "BMIX": 0.001,
        #                                        "AMIX_MAG": 0.8,
        #                                        "BMIX_MAG": 0.001}}}])
        # os.remove(os.path.join(subdir, "error.1.tar.gz"))

    def test_to_from_dict(self):
        h = UnconvergedErrorHandler("random_name.xml")
        h2 = UnconvergedErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), UnconvergedErrorHandler)
        self.assertEqual(h2.output_filename, "random_name.xml")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)


class PBSWalltimeHandlerTest(unittest.TestCase):

    def test_correct(self):
        h = PBSWalltimeHandler()
        os.chdir(cwd)
        h.correct()
        with open("STOPCAR") as f:
            content = f.read()
            self.assertEqual(content, "LSTOP = .TRUE.")
        os.remove("STOPCAR")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
