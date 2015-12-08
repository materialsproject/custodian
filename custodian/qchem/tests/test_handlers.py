# coding: utf-8

from __future__ import unicode_literals, division
import json

from monty.json import MontyEncoder, MontyDecoder


"""
Created on Dec 6, 2012
"""

import os
import shutil
from unittest import TestCase
import unittest

from pkg_resources import parse_version
import pymatgen
import copy

from custodian.qchem.handlers import QChemErrorHandler
from custodian.qchem.jobs import QchemJob


__author__ = "Xiaohui Qu"
__version__ = "0.1"
__maintainer__ = "Xiaohui Qu"
__email__ = "xqu@lbl.gov"
__date__ = "Dec 6, 2013"

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "test_files", "qchem")
# noinspection PyUnresolvedReferences
scr_dir = os.path.join(test_dir, "scr")


class QChemErrorHandlerTest(TestCase):
    def setUp(self):
        os.makedirs(scr_dir)
        os.chdir(scr_dir)


    @classmethod
    def _revert_scf_fix_strategy_to_version(cls, old_lines, fix_version="1.0"):
        old_lines = copy.deepcopy(old_lines)
        start_index = 0
        end_index = 0
        for i, v in enumerate(old_lines):
            if "<SCF Fix Strategy>" in v:
                start_index = i + 1
                break
        for i, v in enumerate(old_lines):
            if "</SCF Fix Strategy>" in v:
                end_index = i
                break
        old_strategy_text = old_lines[start_index: end_index]
        old_strategy = json.loads("\n".join(["{"] + old_strategy_text + ["}"]))
        target_version_strategy = dict()
        if fix_version == "1.0":
            target_version_strategy["current_method_id"] = old_strategy["current_method_id"]
            if old_strategy["methods"][1] == "rca_diis":
                methods_list = ["increase_iter", "rca_diis", "gwh",
                                "gdm", "rca", "core+rca"]
            else:
                methods_list = ["increase_iter", "diis_gdm", "gwh",
                                "rca", "gdm", "core+gdm"]
            target_version_strategy["methods"] = methods_list
        elif fix_version == "2.0":
            target_version_strategy["current_method_id"] = old_strategy["current_method_id"]
            if old_strategy["methods"][1] == "rca_diis":
                methods_list = ["increase_iter", "rca_diis", "gwh",
                                "gdm", "rca", "core+rca", "fon"]
            else:
                methods_list = ["increase_iter", "diis_gdm", "gwh",
                                "rca", "gdm", "core+gdm", "fon"]
            target_version_strategy["methods"] = methods_list
            target_version_strategy["version"] = old_strategy["version"]
        else:
            raise ValueError("Revert to SCF Fix Strategy Version \"{}\" is not "
                             "supported yet".format(fix_version))
        target_version_strategy_text = json.dumps(target_version_strategy,
                                                  indent=4, sort_keys=True)
        stripped_target_stragy_lines = [line.strip() for line in
                                        target_version_strategy_text.split("\n")]
        target_lines = copy.deepcopy(old_lines)
        target_lines[start_index: end_index] = stripped_target_stragy_lines[1: -1]
        return target_lines


    def test_scf_rca(self):
        shutil.copyfile(os.path.join(test_dir, "hf_rca.inp"),
                        os.path.join(scr_dir, "hf_rca.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['increase_iter']})
        with open(os.path.join(test_dir, "hf_rca_tried_0.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        ans = self._revert_scf_fix_strategy_to_version(ans, fix_version="1.0")
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_0.inp"),
                        os.path.join(scr_dir, "hf_rca_tried_0.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_tried_0.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['rca_diis']})
        with open(os.path.join(test_dir, "hf_rca_tried_1.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca_tried_0.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_1.inp"),
                        os.path.join(scr_dir, "hf_rca_tried_1.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_tried_1.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['gwh']})
        with open(os.path.join(test_dir, "hf_rca_tried_2.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca_tried_1.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_2.inp"),
                        os.path.join(scr_dir, "hf_rca_tried_2.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_tried_2.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['gdm']})
        with open(os.path.join(test_dir, "hf_rca_tried_3.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca_tried_2.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_3.inp"),
                        os.path.join(scr_dir, "hf_rca_tried_3.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_tried_3.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['rca']})
        with open(os.path.join(test_dir, "hf_rca_tried_4.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca_tried_3.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_4.inp"),
                        os.path.join(scr_dir, "hf_rca_tried_4.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_tried_4.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['core+rca']})
        with open(os.path.join(test_dir, "hf_rca_tried_5.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca_tried_4.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_5.inp"),
                        os.path.join(scr_dir, "hf_rca_tried_5.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_tried_5.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': None})


    def test_scf_fon(self):
        shutil.copyfile(os.path.join(test_dir, "hf_rca_hit_5.inp"),
                        os.path.join(scr_dir, "hf_rca_hit_5.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_rca.out"),
                        os.path.join(scr_dir, "hf_rca.out"))
        h = QChemErrorHandler(input_file="hf_rca_hit_5.inp",
                              output_file="hf_rca.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['fon']})
        with open(os.path.join(test_dir, "hf_rca_hit_5_fon.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_rca_hit_5.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        ans = self._revert_scf_fix_strategy_to_version(ans, fix_version="2.0")
        self.assertEqual(ref, ans)


    def test_negative_eigen(self):
        shutil.copyfile(os.path.join(test_dir, "negative_eigen.qcinp"),
                        os.path.join(scr_dir, "negative_eigen.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "negative_eigen.qcout"),
                        os.path.join(scr_dir, "negative_eigen.qcout"))
        h = QChemErrorHandler(input_file="negative_eigen.qcinp",
                              output_file="negative_eigen.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Molecular charge is not found',
                                        'Negative Eigen'],
                             'actions': ['use tight integral threshold']})
        with open(os.path.join(test_dir, "negative_eigen_tried_1.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "negative_eigen.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "negative_eigen_tried_1.qcinp"),
                        os.path.join(scr_dir, "negative_eigen_tried_1.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "negative_eigen.qcout"),
                        os.path.join(scr_dir, "negative_eigen.qcout"))
        h = QChemErrorHandler(input_file="negative_eigen_tried_1.qcinp",
                              output_file="negative_eigen.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Molecular charge is not found',
                                        'Negative Eigen'],
                             'actions': ['use even tighter integral threshold']})
        with open(os.path.join(test_dir, "negative_eigen_tried_2.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "negative_eigen_tried_1.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_no_error(self):
        shutil.copyfile(os.path.join(test_dir, "hf_no_error.inp"),
                        os.path.join(scr_dir, "hf_no_error.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_no_error.out"),
                        os.path.join(scr_dir, "hf_no_error.out"))
        h = QChemErrorHandler(input_file="hf_no_error.inp",
                              output_file="hf_no_error.out")
        has_error = h.check()
        self.assertFalse(has_error)

    def test_scf_reset(self):
        shutil.copyfile(os.path.join(test_dir, "hf_rca_tried_1.inp"),
                        os.path.join(scr_dir, "hf_scf_reset.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_scf_reset.out"),
                        os.path.join(scr_dir, "hf_scf_reset.out"))
        h = QChemErrorHandler(input_file="hf_scf_reset.inp",
                              output_file="hf_scf_reset.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed'],
                             'actions': ['reset']})
        with open(os.path.join(test_dir, "hf_scf_reset.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_scf_reset.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_unable_to_determine_lambda(self):
        shutil.copyfile(os.path.join(test_dir, "unable_to_determine_lambda_in_geom_opt.qcinp"),
                        os.path.join(scr_dir, "unable_to_determine_lambda_in_geom_opt.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "unable_to_determine_lambda_in_geom_opt.qcout"),
                        os.path.join(scr_dir, "unable_to_determine_lambda_in_geom_opt.qcout"))
        h = QChemErrorHandler(input_file="unable_to_determine_lambda_in_geom_opt.qcinp",
                              output_file="unable_to_determine_lambda_in_geom_opt.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Geometry optimization failed',
                                        'Lamda Determination Failed'],
                             'actions': ['reset']})
        with open(os.path.join(test_dir, "unable_to_determine_lambda_in_geom_opt_reset.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "unable_to_determine_lambda_in_geom_opt.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_scf_gdm(self):
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.inp"),
                        os.path.join(scr_dir, "hf_gdm.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['increase_iter']})
        with open(os.path.join(test_dir, "hf_gdm_tried_0.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_gdm.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        ans = self._revert_scf_fix_strategy_to_version(ans, fix_version="1.0")
        self.assertEqual(ref, ans)
        shutil.copyfile(os.path.join(test_dir, "hf_gdm_tried_0.inp"),
                        os.path.join(scr_dir, "hf_gdm_tried_0.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm_tried_0.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['diis_gdm']})
        with open(os.path.join(test_dir, "hf_gdm_tried_1.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_gdm_tried_0.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_gdm_tried_1.inp"),
                        os.path.join(scr_dir, "hf_gdm_tried_1.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm_tried_1.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['gwh']})
        with open(os.path.join(test_dir, "hf_gdm_tried_2.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_gdm_tried_1.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_gdm_tried_2.inp"),
                        os.path.join(scr_dir, "hf_gdm_tried_2.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm_tried_2.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['rca']})
        with open(os.path.join(test_dir, "hf_gdm_tried_3.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_gdm_tried_2.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_gdm_tried_3.inp"),
                        os.path.join(scr_dir, "hf_gdm_tried_3.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm_tried_3.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['gdm']})
        with open(os.path.join(test_dir, "hf_gdm_tried_4.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_gdm_tried_3.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_gdm_tried_4.inp"),
                        os.path.join(scr_dir, "hf_gdm_tried_4.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm_tried_4.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['core+gdm']})
        with open(os.path.join(test_dir, "hf_gdm_tried_5.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_gdm_tried_4.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_gdm_tried_5.inp"),
                        os.path.join(scr_dir, "hf_gdm_tried_5.inp"))
        shutil.copyfile(os.path.join(test_dir, "hf_gdm.out"),
                        os.path.join(scr_dir, "hf_gdm.out"))
        h = QChemErrorHandler(input_file="hf_gdm_tried_5.inp",
                              output_file="hf_gdm.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': None})

    def test_opt_failed(self):
        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed.qcinp"),
                        os.path.join(scr_dir, "hf_opt_failed.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed.qcout"),
                        os.path.join(scr_dir, "hf_opt_failed.qcout"))
        h = QChemErrorHandler(input_file="hf_opt_failed.qcinp",
                              output_file="hf_opt_failed.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Geometry optimization failed'],
                             'actions': ['increase_iter']})
        with open(os.path.join(test_dir, "hf_opt_failed_tried_0.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_opt_failed.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed_tried_0.qcinp"),
                        os.path.join(scr_dir, "hf_opt_failed_tried_0.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed.qcout"),
                        os.path.join(scr_dir, "hf_opt_failed.qcout"))
        h = QChemErrorHandler(input_file="hf_opt_failed_tried_0.qcinp",
                              output_file="hf_opt_failed.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Geometry optimization failed'],
                             'actions': ['GDIIS']})
        with open(os.path.join(test_dir, "hf_opt_failed_tried_1.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_opt_failed_tried_0.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed_tried_1.qcinp"),
                        os.path.join(scr_dir, "hf_opt_failed_tried_1.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed.qcout"),
                        os.path.join(scr_dir, "hf_opt_failed.qcout"))
        h = QChemErrorHandler(input_file="hf_opt_failed_tried_1.qcinp",
                              output_file="hf_opt_failed.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Geometry optimization failed'],
                             'actions': ['CartCoords']})
        with open(os.path.join(test_dir, "hf_opt_failed_tried_2.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "hf_opt_failed_tried_1.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed_tried_2.qcinp"),
                        os.path.join(scr_dir, "hf_opt_failed_tried_2.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "hf_opt_failed.qcout"),
                        os.path.join(scr_dir, "hf_opt_failed.qcout"))
        h = QChemErrorHandler(input_file="hf_opt_failed_tried_2.qcinp",
                              output_file="hf_opt_failed.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Geometry optimization failed'],
                             'actions': None})

    def test_autoz_error(self):
        shutil.copyfile(os.path.join(test_dir, "qunino_vinyl.qcinp"),
                        os.path.join(scr_dir, "qunino_vinyl.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "qunino_vinyl.qcout"),
                        os.path.join(scr_dir, "qunino_vinyl.qcout"))
        h = QChemErrorHandler(input_file="qunino_vinyl.qcinp",
                              output_file="qunino_vinyl.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found',
                                        'autoz error'],
                             'actions': ['disable symmetry']})
        with open(os.path.join(test_dir, "qunino_vinyl_nosymm.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "qunino_vinyl.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

        shutil.copyfile(os.path.join(test_dir, "qunino_vinyl_nosymm.qcinp"),
                        os.path.join(scr_dir, "qunino_vinyl_nosymm.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "qunino_vinyl.qcout"),
                        os.path.join(scr_dir, "qunino_vinyl.qcout"))
        h = QChemErrorHandler(input_file="qunino_vinyl_nosymm.qcinp",
                              output_file="qunino_vinyl.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found',
                                        'autoz error'],
                             'actions': None})

    def test_nan_error(self):
        shutil.copyfile(os.path.join(test_dir, "thiane_nan.inp"),
                        os.path.join(scr_dir, "thiane_nan.inp"))
        shutil.copyfile(os.path.join(test_dir, "thiane_nan.out"),
                        os.path.join(scr_dir, "thiane_nan.out"))
        h = QChemErrorHandler(input_file="thiane_nan.inp",
                              output_file="thiane_nan.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['NAN values'],
                             'actions': ['use tighter grid']})
        with open(os.path.join(test_dir, "thiane_nan_dense_grid.inp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "thiane_nan.inp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)
        shutil.copyfile(os.path.join(test_dir, "thiane_nan_dense_grid.inp"),
                        os.path.join(scr_dir, "thiane_nan_dense_grid.inp"))
        shutil.copyfile(os.path.join(test_dir, "thiane_nan.out"),
                        os.path.join(scr_dir, "thiane_nan.out"))
        h = QChemErrorHandler(input_file="thiane_nan_dense_grid.inp",
                              output_file="thiane_nan.out")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['NAN values'],
                             'actions': None})

        shutil.copyfile(os.path.join(test_dir, "h2o_nan.qcinp"),
                        os.path.join(scr_dir, "h2o_nan.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "h2o_nan.qcout"),
                        os.path.join(scr_dir, "h2o_nan.qcout"))
        h = QChemErrorHandler(input_file="h2o_nan.qcinp",
                              output_file="h2o_nan.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['NAN values'],
                             'actions': ['use tighter grid']})
        with open(os.path.join(test_dir, "h2o_nan_dense_grid.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "h2o_nan.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_no_input_text(self):
        shutil.copyfile(os.path.join(test_dir, "no_reading.qcinp"),
                        os.path.join(scr_dir, "no_reading.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "no_reading.qcout"),
                        os.path.join(scr_dir, "no_reading.qcout"))
        h = QChemErrorHandler(input_file="no_reading.qcinp",
                              output_file="no_reading.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Exit Code 134',
                                        'Molecular charge is not found',
                                        'No input text'],
                             'actions': ['disable symmetry']})
        with open(os.path.join(test_dir, "no_reading_nosymm.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "no_reading.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_exit_code_134(self):
        shutil.copyfile(os.path.join(test_dir, "exit_code_134.qcinp"),
                        os.path.join(scr_dir, "exit_code_134.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "exit_code_134.qcout"),
                        os.path.join(scr_dir, "exit_code_134.qcout"))
        h = QChemErrorHandler(input_file="exit_code_134.qcinp",
                              output_file="exit_code_134.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Exit Code 134',
                                        'Molecular charge is not found'],
                             'actions': ['use tight integral threshold']})
        with open(os.path.join(test_dir, "exit_code_134_tight_thresh.qcinp"))\
                as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "exit_code_134.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_exit_code_134_after_scf_fix(self):
        shutil.copyfile(os.path.join(test_dir, "exit_134_after_scf_fix.qcinp"),
                        os.path.join(scr_dir, "exit_134_after_scf_fix.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "exit_134_after_scf_fix.qcout"),
                        os.path.join(scr_dir, "exit_134_after_scf_fix.qcout"))
        h = QChemErrorHandler(input_file="exit_134_after_scf_fix.qcinp",
                              output_file="exit_134_after_scf_fix.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Exit Code 134',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['use tight integral threshold']})
        with open(os.path.join(test_dir, "exit_134_after_scf_fix_tight_thresh.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "exit_134_after_scf_fix.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)
        shutil.copyfile(os.path.join(test_dir, "exit_134_after_scf_fix_tight_thresh.qcinp"),
                        os.path.join(scr_dir, "exit_134_after_scf_fix_tight_thresh.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "exit_134_after_scf_fix.qcout"),
                        os.path.join(scr_dir, "exit_134_after_scf_fix.qcout"))
        qchem_job = QchemJob(qchem_cmd="qchem -np 24",
                             input_file="exit_134_after_scf_fix_tight_thresh.qcinp",
                             output_file="exit_134_after_scf_fix.qcout",
                             alt_cmd={"half_cpus": "qchem -np 12",
                                      "openmp": "qchem -nt 24"})
        h = QChemErrorHandler(input_file="exit_134_after_scf_fix_tight_thresh.qcinp",
                              output_file="exit_134_after_scf_fix.qcout",
                              qchem_job=qchem_job)
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Exit Code 134',
                                        'Geometry optimization failed',
                                        'Molecular charge is not found'],
                             'actions': ['openmp']})

    def test_ts_opt(self):
        shutil.copyfile(os.path.join(test_dir, "ts_cf3_leave.qcinp"),
                        os.path.join(scr_dir, "ts_cf3_leave.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "ts_cf3_leave.qcout"),
                        os.path.join(scr_dir, "ts_cf3_leave.qcout"))
        h = QChemErrorHandler(input_file="ts_cf3_leave.qcinp",
                              output_file="ts_cf3_leave.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Exit Code 134',
                                        'Geometry optimization failed'],
                             'actions': ['increase_iter']})
        with open(os.path.join(test_dir, "ts_cf3_leave_reset_first_step_mol.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "ts_cf3_leave.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_scf_in_aimd_reset(self):
        shutil.copyfile(os.path.join(test_dir, "h2o_aimd.qcinp"),
                        os.path.join(scr_dir, "h2o_aimd.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "h2o_aimd.qcout"),
                        os.path.join(scr_dir, "h2o_aimd.qcout"))
        h = QChemErrorHandler(input_file="h2o_aimd.qcinp",
                              output_file="h2o_aimd.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence'],
                             'actions': ['reset']})
        with open(os.path.join(test_dir, "h2o_aimd_reset.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "h2o_aimd.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_freq_job_too_small(self):
        shutil.copyfile(os.path.join(test_dir, "freq_seg_too_small.qcinp"),
                        os.path.join(scr_dir, "freq_seg_too_small.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "freq_seg_too_small.qcout"),
                        os.path.join(scr_dir, "freq_seg_too_small.qcout"))
        h = QChemErrorHandler(input_file="freq_seg_too_small.qcinp",
                              output_file="freq_seg_too_small.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Exit Code 134',
                                        'Freq Job Too Small'],
                             'actions': ['use 31 segment in CPSCF']})
        with open(os.path.join(test_dir, "freq_seg_too_small_31_segments.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "freq_seg_too_small.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)
        shutil.copyfile(os.path.join(test_dir, "freq_seg_too_small_31_segments.qcinp"),
                        os.path.join(scr_dir, "freq_seg_too_small_31_segments.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "freq_seg_too_small.qcout"),
                        os.path.join(scr_dir, "freq_seg_too_small.qcout"))
        h = QChemErrorHandler(input_file="freq_seg_too_small_31_segments.qcinp",
                              output_file="freq_seg_too_small.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Exit Code 134',
                                        'Freq Job Too Small'],
                             'actions': None})

    @unittest.skipIf(parse_version(pymatgen.__version__) <=
                     parse_version('3.2.3'),
                     "New QChem 4.2 PCM format in pymatgen is a feature after "
                     "version 3.2.3")
    def test_pcm_solvent_deprecated(self):
        shutil.copyfile(os.path.join(test_dir, "pcm_solvent_deprecated.qcinp"),
                        os.path.join(scr_dir, "pcm_solvent_deprecated.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "pcm_solvent_deprecated.qcout"),
                        os.path.join(scr_dir, "pcm_solvent_deprecated.qcout"))
        h = QChemErrorHandler(input_file="pcm_solvent_deprecated.qcinp",
                              output_file="pcm_solvent_deprecated.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Bad SCF convergence',
                                        'Molecular charge is not found',
                                        'No input text',
                                        'pcm_solvent deprecated'],
                             'actions': ['use keyword solvent instead']})
        with open(os.path.join(test_dir, "pcm_solvent_deprecated_use_qc42_format.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "pcm_solvent_deprecated.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)

    def test_not_enough_total_memory(self):
        old_jobid = os.environ.get("PBS_JOBID", None)
        os.environ["PBS_JOBID"] = "hopque473945"
        shutil.copyfile(os.path.join(test_dir, "not_enough_total_memory.qcinp"),
                        os.path.join(scr_dir, "not_enough_total_memory.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "not_enough_total_memory.qcout"),
                        os.path.join(scr_dir, "not_enough_total_memory.qcout"))
        h = QChemErrorHandler(input_file="not_enough_total_memory.qcinp",
                              output_file="not_enough_total_memory.qcout")
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Exit Code 134',
                                        'Not Enough Total Memory'],
                             'actions': ['Use 48 CPSCF segments']})
        with open(os.path.join(test_dir, "not_enough_total_memory_48_segments.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "not_enough_total_memory.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)
        shutil.copyfile(os.path.join(test_dir, "not_enough_total_memory_48_segments.qcinp"),
                        os.path.join(scr_dir, "not_enough_total_memory_48_segments.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "not_enough_total_memory.qcout"),
                        os.path.join(scr_dir, "not_enough_total_memory.qcout"))
        qchem_job = QchemJob(qchem_cmd=["qchem", "-np", "24"],
                             alt_cmd={"openmp": ["qchem", "-seq", "-nt", "24"],
                                      "half_cpus": ["qchem", "-np", "12"]},
                             input_file="not_enough_total_memory_48_segments.qcinp")
        h = QChemErrorHandler(input_file="not_enough_total_memory_48_segments.qcinp",
                              output_file="not_enough_total_memory.qcout",
                              qchem_job=qchem_job)
        has_error = h.check()
        self.assertTrue(has_error)
        d = h.correct()
        self.assertEqual(d, {'errors': ['Exit Code 134',
                                        'Not Enough Total Memory'],
                             'actions': ['Use half CPUs and 60 CPSCF segments']})
        with open(os.path.join(test_dir, "not_enough_total_memory_60_segments.qcinp")) as f:
            ref = [line.strip() for line in f.readlines()]
        with open(os.path.join(scr_dir, "not_enough_total_memory_48_segments.qcinp")) as f:
            ans = [line.strip() for line in f.readlines()]
        self.assertEqual(ref, ans)
        if old_jobid is None:
            os.environ.pop("PBS_JOBID")
        else:
            os.environ["PBS_JOBID"] = old_jobid

    def test_json_serializable(self):
        q1 = QChemErrorHandler()
        str1 = json.dumps(q1, cls=MontyEncoder)
        q2 = json.loads(str1, cls=MontyDecoder)
        self.assertEqual(q1.as_dict(), q2.as_dict())
        shutil.copyfile(os.path.join(test_dir, "qunino_vinyl.qcinp"),
                        os.path.join(scr_dir, "qunino_vinyl.qcinp"))
        shutil.copyfile(os.path.join(test_dir, "qunino_vinyl.qcout"),
                        os.path.join(scr_dir, "qunino_vinyl.qcout"))
        q3 = QChemErrorHandler(input_file="qunino_vinyl.qcinp",
                               output_file="qunino_vinyl.qcout")
        q3.check()
        q3.correct()
        for od in q3.outdata:
            od.pop("input")
        str3 = json.dumps(q3, cls=MontyEncoder)
        q4 = json.loads(str3, cls=MontyDecoder)
        self.assertEqual(q3.as_dict(), q4.as_dict())

    def tearDown(self):
        shutil.rmtree(scr_dir)
        pass


if __name__ == "__main__":
    unittest.main()
