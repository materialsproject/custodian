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

import multiprocessing
from custodian.vasp.jobs import VaspJob
from pymatgen.io.vaspio import Incar

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files')


class VaspJobTest(unittest.TestCase):

    def test_to_from_dict(self):
        v = VaspJob("hello")
        v2 = VaspJob.from_dict(v.to_dict)
        self.assertEqual(type(v2), type(v))
        self.assertEqual(v2.vasp_cmd, "hello")

    def test_setup(self):
        if "VASP_PSP_DIR" not in os.environ:
            os.environ["VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        v = VaspJob("hello")
        v.setup()
        incar = Incar.from_file("INCAR")
        count = multiprocessing.cpu_count()
        if count > 1:
            self.assertGreater(incar["NPAR"], 1)
        shutil.copy("INCAR.orig", "INCAR")
        os.remove("INCAR.orig")
        os.remove("KPOINTS.orig")
        os.remove("POTCAR.orig")
        os.remove("POSCAR.orig")

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
