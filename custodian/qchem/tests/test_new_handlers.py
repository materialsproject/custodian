# coding: utf-8

from __future__ import unicode_literals, division
import json
import shlex

from monty.json import MontyEncoder, MontyDecoder


"""
Created on March 27, 2018
"""

import os
import shutil
from unittest import TestCase
import unittest

from pkg_resources import parse_version
import pymatgen
import copy

from custodian.qchem.new_handlers import QChemErrorHandler
from custodian.qchem.new_jobs import QCJob


__author__ = "Samuel Blau, Brandon Woods, Shyam Dwaraknath"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/26/18"


test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "test_files", "qchem")
# noinspection PyUnresolvedReferences
scr_dir = os.path.join(test_dir, "scr")
cwd = os.getcwd()

class QChemErrorHandlerTest(TestCase):


    def test(self):
        h = QChemErrorHandler(input_file="/Users/samuelblau/Desktop/test.qin",
                              output_file="/Users/samuelblau/Desktop/test.qout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': ['increase_iter']})
        # with open(os.path.join(test_dir, "hf_rca_tried_0.inp")) as f:
        #     ref = [line.strip() for line in f.readlines()]
        # with open(os.path.join(scr_dir, "hf_rca.inp")) as f:
        #     ans = [line.strip() for line in f.readlines()]
        # ans = self._revert_scf_fix_strategy_to_version(ans, fix_version="1.0")
        # self.assertEqual(ref, ans)

        # shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_0.inp"),
        #                 os.path.join(scr_dir, "hf_rca_tried_0.inp"))
        # shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
        #                 os.path.join(scr_dir, "hf_rca.out"))
        # h = QChemErrorHandler(input_file="hf_rca_tried_0.inp",
        #                       output_file="hf_rca.out")
        # has_error = h.check()
        # self.assertTrue(has_error)
        # d = h.correct()
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': ['rca_diis']})
        # with open(os.path.join(test_dir, "hf_rca_tried_1.inp")) as f:
        #     ref = [line.strip() for line in f.readlines()]
        # with open(os.path.join(scr_dir, "hf_rca_tried_0.inp")) as f:
        #     ans = [line.strip() for line in f.readlines()]
        # self.assertEqual(ref, ans)

        # shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_1.inp"),
        #                 os.path.join(scr_dir, "hf_rca_tried_1.inp"))
        # shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
        #                 os.path.join(scr_dir, "hf_rca.out"))
        # h = QChemErrorHandler(input_file="hf_rca_tried_1.inp",
        #                       output_file="hf_rca.out")
        # has_error = h.check()
        # self.assertTrue(has_error)
        # d = h.correct()
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': ['gwh']})
        # with open(os.path.join(test_dir, "hf_rca_tried_2.inp")) as f:
        #     ref = [line.strip() for line in f.readlines()]
        # with open(os.path.join(scr_dir, "hf_rca_tried_1.inp")) as f:
        #     ans = [line.strip() for line in f.readlines()]
        # self.assertEqual(ref, ans)

        # shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_2.inp"),
        #                 os.path.join(scr_dir, "hf_rca_tried_2.inp"))
        # shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
        #                 os.path.join(scr_dir, "hf_rca.out"))
        # h = QChemErrorHandler(input_file="hf_rca_tried_2.inp",
        #                       output_file="hf_rca.out")
        # has_error = h.check()
        # self.assertTrue(has_error)
        # d = h.correct()
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': ['gdm']})
        # with open(os.path.join(test_dir, "hf_rca_tried_3.inp")) as f:
        #     ref = [line.strip() for line in f.readlines()]
        # with open(os.path.join(scr_dir, "hf_rca_tried_2.inp")) as f:
        #     ans = [line.strip() for line in f.readlines()]
        # self.assertEqual(ref, ans)

        # shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_3.inp"),
        #                 os.path.join(scr_dir, "hf_rca_tried_3.inp"))
        # shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
        #                 os.path.join(scr_dir, "hf_rca.out"))
        # h = QChemErrorHandler(input_file="hf_rca_tried_3.inp",
        #                       output_file="hf_rca.out")
        # has_error = h.check()
        # self.assertTrue(has_error)
        # d = h.correct()
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': ['rca']})
        # with open(os.path.join(test_dir, "hf_rca_tried_4.inp")) as f:
        #     ref = [line.strip() for line in f.readlines()]
        # with open(os.path.join(scr_dir, "hf_rca_tried_3.inp")) as f:
        #     ans = [line.strip() for line in f.readlines()]
        # self.assertEqual(ref, ans)

        # shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_4.inp"),
        #                 os.path.join(scr_dir, "hf_rca_tried_4.inp"))
        # shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
        #                 os.path.join(scr_dir, "hf_rca.out"))
        # h = QChemErrorHandler(input_file="hf_rca_tried_4.inp",
        #                       output_file="hf_rca.out")
        # has_error = h.check()
        # self.assertTrue(has_error)
        # d = h.correct()
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': ['core+rca']})
        # with open(os.path.join(test_dir, "hf_rca_tried_5.inp")) as f:
        #     ref = [line.strip() for line in f.readlines()]
        # with open(os.path.join(scr_dir, "hf_rca_tried_4.inp")) as f:
        #     ans = [line.strip() for line in f.readlines()]
        # self.assertEqual(ref, ans)

        # shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_5.inp"),
        #                 os.path.join(scr_dir, "hf_rca_tried_5.inp"))
        # shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
        #                 os.path.join(scr_dir, "hf_rca.out"))
        # h = QChemErrorHandler(input_file="hf_rca_tried_5.inp",
        #                       output_file="hf_rca.out")
        # has_error = h.check()
        # self.assertTrue(has_error)
        # d = h.correct()
        # self.assertEqual(d, {'errors': ['Bad SCF convergence',
        #                                 'Geometry optimization failed',
        #                                 'Molecular charge is not found'],
        #                      'actions': None})

if __name__ == "__main__":
    unittest.main()
