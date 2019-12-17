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
from monty.os import cd
from monty.tempfile import ScratchDir
from custodian.feff.jobs import FeffJob
from pymatgen.io.feff.inputs import Atoms, Tags

test_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "test_files", "feff_unconverge"
)


class FeffJobTest(unittest.TestCase):
    def test_to_from_dict(self):
        f = FeffJob("hello")
        f2 = FeffJob.from_dict(f.as_dict())
        self.assertEqual(type(f), type(f2))
        self.assertEqual(f2.feff_cmd, "hello")

    def test_setup(self):
        with cd(test_dir):
            with ScratchDir(".", copy_from_current_on_enter=True):
                f = FeffJob("hello", backup=True)
                f.setup()

                parameter = Tags.from_file("feff.inp")
                parameter_orig = Tags.from_file("feff.inp.orig")
                self.assertEqual(parameter, parameter_orig)

                atom = Atoms.cluster_from_file("feff.inp")
                atom_origin = Atoms.cluster_from_file("feff.inp.orig")
                self.assertEqual(atom, atom_origin)

    def test_postprocess(self):
        with cd(test_dir):
            with ScratchDir(".", copy_from_current_on_enter=True):
                f = FeffJob("hello", backup=True, gzipped=True)
                f.postprocess()
                self.assertTrue(os.path.exists("feff_out.1.tar.gz"))
                f.postprocess()
                self.assertTrue(os.path.exists("feff_out.2.tar.gz"))
