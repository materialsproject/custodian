import os
import shutil
import unittest
from glob import glob

from custodian import TEST_FILES
from custodian.feff.handlers import UnconvergedErrorHandler

__author__ = "Chen Zheng"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Chen Zheng"
__email__ = "chz022@ucsd.edu"
__date__ = "Oct 18, 2017"


def clean_dir():
    for f in glob("error.*.tar.gz"):
        os.remove(f)


class UnconvergedErrorHandlerTest(unittest.TestCase):
    def setUp(self):
        os.chdir(TEST_FILES)
        subdir = f"{TEST_FILES}/feff_unconverged"
        os.chdir(subdir)
        shutil.copy("ATOMS", "ATOMS.orig")
        shutil.copy("PARAMETERS", "PARAMETERS.orig")
        shutil.copy("HEADER", "HEADER.orig")
        shutil.copy("POTENTIALS", "POTENTIALS.orig")
        shutil.copy("feff.inp", "feff.inp.orig")
        shutil.copy("log1.dat", "log1.dat.orig")

    def test_check_unconverged(self):
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Non-converging job"]
        assert dct["actions"] == [
            {"dict": "PARAMETERS", "action": {"_set": {"RESTART": []}}},
            {"action": {"_set": {"SCF": [7, 0, 100, 0.2, 3]}}, "dict": "PARAMETERS"},
        ]
        shutil.move("ATOMS.orig", "ATOMS")
        shutil.move("PARAMETERS.orig", "PARAMETERS")
        shutil.move("HEADER.orig", "HEADER")
        shutil.move("POTENTIALS.orig", "POTENTIALS")
        shutil.move("feff.inp.orig", "feff.inp")
        shutil.move("log1.dat.orig", "log1.dat")
        clean_dir()
