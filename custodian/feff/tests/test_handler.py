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

from custodian.feff.handlers import UnconvergedErrorHandler

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "test_files")

class UnconvergedErrorHandlerTest(unittest.TestCase):

    def setUp(cls):
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "feff_unconverge")
        os.chdir(subdir)

    def test_check_unconverged(self):
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Non-converging job"])
