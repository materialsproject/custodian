# coding: utf-8

from __future__ import unicode_literals, division

__author__ = "Chen Zheng"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Chen Zheng"
__email__ = "chz022@ucsd.edu"
__date__ = "Oct 18, 2017"

import unittest
import os
import glob
import shutil

from custodian.feff.handlers import UnconvergedErrorHandler

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_files")


def clean_dir():
    for f in glob.glob("error.*.tar.gz"):
        os.remove(f)


class UnconvergedErrorHandlerTest(unittest.TestCase):
    def setUp(cls):
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "feff_unconverge")
        os.chdir(subdir)
        shutil.copy("ATOMS", "ATOMS.orig")
        shutil.copy("PARAMETERS", "PARAMETERS.orig")
        shutil.copy("HEADER", "HEADER.orig")
        shutil.copy("POTENTIALS", "POTENTIALS.orig")
        shutil.copy("feff.inp", "feff.inp.orig")
        shutil.copy("log1.dat", "log1.dat.orig")

    def test_check_unconverged(self):
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Non-converging job"])
        self.assertEqual(
            d["actions"],
            [
                {"dict": "PARAMETERS", "action": {"_set": {"RESTART": []}}},
                {
                    "action": {"_set": {"SCF": [7, 0, 100, 0.2, 3]}},
                    "dict": "PARAMETERS",
                },
            ],
        )
        shutil.move("ATOMS.orig", "ATOMS")
        shutil.move("PARAMETERS.orig", "PARAMETERS")
        shutil.move("HEADER.orig", "HEADER")
        shutil.move("POTENTIALS.orig", "POTENTIALS")
        shutil.move("feff.inp.orig", "feff.inp")
        shutil.move("log1.dat.orig", "log1.dat")
        clean_dir()
