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
from custodian.utils import ScratchDir, \
    recursive_copy
import os
import tempfile
import shutil


class FuncTest(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        os.mkdir("src")
        with open(os.path.join("src", "test"), "w") as f:
            f.write("what")

    def test_recursive_copy(self):
        recursive_copy(".", "dst")
        self.assertTrue(os.path.exists(os.path.join("dst", "src", "test")))
        self.assertTrue(os.path.exists(os.path.join("dst", "__init__.py")))

    def tearDown(self):
        shutil.rmtree("src")
        shutil.rmtree("dst")
        os.chdir(self.cwd)


class ScratchDirTest(unittest.TestCase):

    def test_with(self):
        scratch = tempfile.gettempdir()
        with ScratchDir(scratch) as d:
            with open("scratch_text", "w") as f:
                f.write("write")
            files = os.listdir(d)
            self.assertIn("scratch_text", files)

        #Make sure the tempdir is deleted.
        self.assertFalse(os.path.exists(d))
        files = os.listdir(".")
        self.assertIn("scratch_text", files)
        os.remove("scratch_text")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
