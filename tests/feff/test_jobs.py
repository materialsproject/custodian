__author__ = "Chen Zheng"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Chen Zheng"
__email__ = "chz022@ucsd.edu"
__date__ = "Oct 18, 2017"

import os
import unittest

from monty.os import cd
from monty.tempfile import ScratchDir
from pymatgen.io.feff.inputs import Atoms, Tags

from custodian import TEST_FILES
from custodian.feff.jobs import FeffJob

TEST_DIR = f"{TEST_FILES}/feff_unconverged"


class FeffJobTest(unittest.TestCase):
    def test_to_from_dict(self):
        f = FeffJob("hello")
        f2 = FeffJob.from_dict(f.as_dict())
        assert type(f) == type(f2)
        assert f2.feff_cmd == "hello"

    def test_setup(self):
        with cd(TEST_DIR), ScratchDir(".", copy_from_current_on_enter=True):
            f = FeffJob("hello", backup=True)
            f.setup()

            parameter = Tags.from_file("feff.inp")
            parameter_orig = Tags.from_file("feff.inp.orig")
            assert parameter == parameter_orig

            atom = Atoms.cluster_from_file("feff.inp")
            atom_origin = Atoms.cluster_from_file("feff.inp.orig")
            assert atom == atom_origin

    def test_postprocess(self):
        with cd(TEST_DIR), ScratchDir(".", copy_from_current_on_enter=True):
            f = FeffJob("hello", backup=True, gzipped=True)
            f.postprocess()
            assert os.path.exists("feff_out.1.tar.gz")
            f.postprocess()
            assert os.path.exists("feff_out.2.tar.gz")
