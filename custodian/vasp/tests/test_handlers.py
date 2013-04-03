#!/usr/bin/env python

"""
Created on Jun 1, 2012
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import unittest
import os
import shutil

from custodian.vasp.handlers import VaspErrorHandler, \
    UnconvergedErrorHandler, PoscarErrorHandler, DentetErrorHandler


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')


class VaspErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("KPOINTS", "KPOINTS.orig")
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
        self.assertEqual(d["errors"], ['mesh_symmetry'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'kpoints': [[4, 4, 4]]}},
                           'dict': 'KPOINTS'}])
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        os.remove(os.path.join(test_dir, "error.1.tar.gz"))
        os.remove(os.path.join(test_dir, "error.2.tar.gz"))

    def test_to_from_dict(self):
        h = VaspErrorHandler("random_name")
        h2 = VaspErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), type(h))
        self.assertEqual(h2.output_filename, "random_name")


class UnconvergedErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        subdir = os.path.join(test_dir, "unconverged")
        os.chdir(subdir)
        h = UnconvergedErrorHandler("POTCAR")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['Unconverged'])
        self.assertEqual(d["actions"],
                         [{'file': 'CONTCAR',
                           'action': {'_file_copy': {'dest': 'POSCAR'}}},
                          {'dict': 'INCAR',
                           'action': {'_set': {'ISTART': 1}}}])
        os.remove(os.path.join(subdir, "error.1.tar.gz"))

    def test_to_from_dict(self):
        h = UnconvergedErrorHandler("random_name.xml")
        h2 = UnconvergedErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), UnconvergedErrorHandler)
        self.assertEqual(h2.output_filename, "random_name.xml")


class PoscarErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        subdir = os.path.join(test_dir, "poscar_error")
        os.chdir(subdir)
        shutil.copy("POSCAR", "POSCAR.orig")
        h = PoscarErrorHandler()
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["Rotation matrix"])
        os.remove(os.path.join(subdir, "error.1.tar.gz"))
        shutil.copy("POSCAR.orig", "POSCAR")
        os.remove("POSCAR.orig")

    def test_to_from_dict(self):
        h = PoscarErrorHandler("random_name.out")
        h2 = PoscarErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), PoscarErrorHandler)
        self.assertEqual(h2.output_filename, "random_name.out")


class DentetErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        shutil.copy("INCAR", "INCAR.orig")
        h = DentetErrorHandler("vasp.dentet")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ['dentet'])
        self.assertEqual(d["actions"],
                         [{'action': {'_set': {'ISMEAR': 0}},
                           'dict': 'INCAR'}])
        os.remove(os.path.join(test_dir, "error.1.tar.gz"))
        shutil.move("INCAR.orig", "INCAR")

    def test_to_from_dict(self):
        h = DentetErrorHandler("random_name.out")
        h2 = DentetErrorHandler.from_dict(h.to_dict)
        self.assertEqual(type(h2), DentetErrorHandler)
        self.assertEqual(h2.output_filename, "random_name.out")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
