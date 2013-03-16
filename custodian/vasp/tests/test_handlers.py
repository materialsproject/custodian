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
    UnconvergedErrorHandler, PoscarErrorHandler


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')


class VaspErrorHandlerTest(unittest.TestCase):

    def test_check_correct(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
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
                         [{'action': {'_set': {'kpoints': [[8, 8, 8]]}},
                           'dict': 'KPOINTS'}])
        os.remove(os.path.join(test_dir, "error.1.tar.gz"))
        os.remove(os.path.join(test_dir, "error.2.tar.gz"))


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

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
