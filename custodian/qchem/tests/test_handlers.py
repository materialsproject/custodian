#!/usr/bin/env python

"""
Created on Dec 6, 2012
"""

from __future__ import division
import os
import shutil
from unittest import TestCase
import unittest
from custodian.qchem.handlers import QChemErrorHandler

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
                                        'Molecular charge is not found'],
                             'actions': ['increase_iter']})
        with open(os.path.join(test_dir, "hf_rca_tried_0.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_rca.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['rca_diis']})
        with open(os.path.join(test_dir, "hf_rca_tried_1.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_rca_tried_0.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['gwh']})
        with open(os.path.join(test_dir, "hf_rca_tried_2.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_rca_tried_1.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['gdm']})
        with open(os.path.join(test_dir, "hf_rca_tried_3.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_rca_tried_2.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['rca']})
        with open(os.path.join(test_dir, "hf_rca_tried_4.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_rca_tried_3.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['core+rca']})
        with open(os.path.join(test_dir, "hf_rca_tried_5.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_rca_tried_4.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': None})

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
        self.assertEqual(d, {'errors': ['Bad SCF convergence'],
                             'actions': ['reset']})
        with open(os.path.join(test_dir, "hf_scf_reset.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_scf_reset.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['increase_iter']})
        with open(os.path.join(test_dir, "hf_gdm_tried_0.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_gdm.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['diis_gdm']})
        with open(os.path.join(test_dir, "hf_gdm_tried_1.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_gdm_tried_0.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['gwh']})
        with open(os.path.join(test_dir, "hf_gdm_tried_2.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_gdm_tried_1.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['rca']})
        with open(os.path.join(test_dir, "hf_gdm_tried_3.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_gdm_tried_2.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['gdm']})
        with open(os.path.join(test_dir, "hf_gdm_tried_4.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_gdm_tried_3.inp")) as f:
            ans = f.read()
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
                                        'Molecular charge is not found'],
                             'actions': ['core+gdm']})
        with open(os.path.join(test_dir, "hf_gdm_tried_5.inp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_gdm_tried_4.inp")) as f:
            ans = f.read()
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
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_opt_failed.qcinp")) as f:
            ans = f.read()
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
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_opt_failed_tried_0.qcinp")) as f:
            ans = f.read()
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
            ref = f.read()
        with open(os.path.join(scr_dir, "hf_opt_failed_tried_1.qcinp")) as f:
            ans = f.read()
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
        self.assertEqual(d, {'errors': ['Molecular charge is not found',
                                        'autoz error'],
                             'actions': ['disable symmetry']})
        with open(os.path.join(test_dir, "qunino_vinyl_nosymm.qcinp")) as f:
            ref = f.read()
        with open(os.path.join(scr_dir, "qunino_vinyl.qcinp")) as f:
            ans = f.read()
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
        self.assertEqual(d, {'errors': ['Molecular charge is not found',
                                        'autoz error'],
                             'actions': None})

    def test_NAN_error(self):
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
            ref = f.read()
        with open(os.path.join(scr_dir, "thiane_nan.inp")) as f:
            ans = f.read()
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
            ref = f.read()
        with open(os.path.join(scr_dir, "h2o_nan.qcinp")) as f:
            ans = f.read()
        self.assertEqual(ref, ans)


    def tearDown(self):
        shutil.rmtree(scr_dir)
        pass


if __name__ == "__main__":
    unittest.main()