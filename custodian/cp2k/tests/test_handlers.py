# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
import time
import unittest
import glob
import shutil
from pathlib import Path
import warnings

from custodian.cp2k.interpreter import Cp2kModder
from custodian.cp2k.handlers import (
    FrozenJobErrorHandler,
    UnconvergedScfErrorHandler,
    AbortHandler,
    NumericalPrecisionHandler,
    StdErrHandler,
    get_conv,
)
from pymatgen.io.cp2k.inputs import Keyword, KeywordList
from pymatgen.io.cp2k.sets import StaticSet


def clean_dir(d):
    for f in glob.glob(os.path.join(d, "error.*.tar.gz")):
        os.remove(f)
    for f in glob.glob(os.path.join(d, "custodian.chk.*.tar.gz")):
        os.remove(f)


class HandlerTests(unittest.TestCase):
    def setUp(self):
        warnings.filterwarnings("ignore")

        self.TEST_FILES_DIR = os.path.join(Path(__file__).parent.absolute(), "../../../test_files/cp2k")

        clean_dir(self.TEST_FILES_DIR)

        time.sleep(1)  # for frozenhandler

        shutil.copy(os.path.join(self.TEST_FILES_DIR, "cp2k.inp.orig"), os.path.join(self.TEST_FILES_DIR, "cp2k.inp"))
        shutil.copy(
            os.path.join(self.TEST_FILES_DIR, "cp2k.inp.hybrid.orig"),
            os.path.join(self.TEST_FILES_DIR, "cp2k.inp.hybrid"),
        )

        self.input_file = os.path.join(self.TEST_FILES_DIR, "cp2k.inp")
        self.input_file_hybrid = os.path.join(self.TEST_FILES_DIR, "cp2k.inp.hybrid")

        self.output_file_preconditioner = os.path.join(self.TEST_FILES_DIR, "cp2k.out.precondstuck")
        self.output_file_choleesky = os.path.join(self.TEST_FILES_DIR, "cp2k.out.cholesky")
        self.output_file_imprecise = os.path.join(self.TEST_FILES_DIR, "cp2k.out.imprecise")
        self.output_file_unconverged = os.path.join(self.TEST_FILES_DIR, "cp2k.out.unconverged")
        self.output_file_stderr = os.path.join(self.TEST_FILES_DIR, "std_err.txt")
        self.output_file_hybrid = os.path.join(self.TEST_FILES_DIR, "cp2k.out.hybrid")
        self.output_file_conv = os.path.join(self.TEST_FILES_DIR, "cp2k.out.conv")

        self.modder = Cp2kModder(filename=self.input_file)

    def test(self):
        kwdlst = KeywordList(
            keywords=[Keyword("BASIS_SET_FILE_NAME", "FILE1"), Keyword("BASIS_SET_FILE_NAME", "FILE2")]
        )
        actions = [
            {"dict": self.input_file, "action": {"_set": {"FORCE_EVAL": {"METHOD": "NOT QA"}}}},
            {"dict": self.input_file, "action": {"_set": {"FORCE_EVAL": {"DFT": {"BASIS_SET_FILE_NAME": kwdlst}}}}},
            {
                "dict": self.input_file,
                "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MAX_SCF": 50}, "OUTER_SCF": {"MAX_SCF": 8}}}}},
            },
        ]
        self.modder.apply_actions(actions=actions)
        self.assertEqual(self.modder.ci["FORCE_EVAL"]["METHOD"], Keyword("METHOD", "NOT QA"))
        self.assertIsInstance(self.modder.ci["FORCE_EVAL"]["DFT"]["BASIS_SET_FILE_NAME"], KeywordList)

    def test_frozenjobhandler(self):
        h = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_preconditioner, timeout=1)
        self.assertTrue(h.check())
        ci = StaticSet.from_file(self.input_file)
        self.assertEqual(
            ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECONDITIONER"], Keyword("PRECONDITIONER", "FULL_SINGLE_INVERSE")
        )
        h.correct()

        ci = StaticSet.from_file(self.input_file)
        self.assertEqual(ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECONDITIONER"], Keyword("PRECONDITIONER", "FULL_ALL"))

        h = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_preconditioner, timeout=1)
        self.assertTrue(h.check())
        h.correct()
        ci = StaticSet.from_file(self.input_file)
        self.assertEqual(ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECOND_SOLVER"], Keyword("PRECOND_SOLVER", "DIRECT"))

        h = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_imprecise, timeout=1)
        h.check()

    def test_uncoverge_handler(self):
        ci = StaticSet.from_file(self.input_file)
        self.assertEqual(ci["force_eval"]["dft"]["scf"]["ot"]["minimizer"], Keyword("MINIMIZER", "DIIS"))
        h = UnconvergedScfErrorHandler(input_file=self.input_file, output_file=self.output_file_unconverged)
        h.check()
        actions = h.correct()
        self.assertTrue(actions["errors"], ["Non-converging Job"])
        ci = StaticSet.from_file(self.input_file)
        self.assertEqual(ci["force_eval"]["dft"]["scf"]["ot"]["minimizer"], Keyword("MINIMIZER", "CG"))

    def test_abort_handler(self):
        h = AbortHandler(input_file=self.input_file, output_file=self.output_file_choleesky)
        self.assertTrue(h.check())

    def test_imprecision_handler(self):

        # Hybrid
        h = NumericalPrecisionHandler(self.input_file_hybrid, output_file=self.output_file_imprecise)
        self.assertTrue(h.check())
        c = h.correct()
        self.assertTrue(c["errors"], ["Unsufficient precision"])

        # Normal
        h = NumericalPrecisionHandler(self.input_file, output_file=self.output_file_imprecise)
        c = h.correct()
        modder = Cp2kModder(filename=self.input_file)
        modder.apply_actions(actions=c["actions"])
        self.assertEqual(modder.ci["force_eval"]["dft"]["xc"]["xc_grid"].get("USE_FINER_GRID").values[0], True)

    def test_std_out(self):
        h = StdErrHandler(output_file=self.output_file_hybrid, std_err=self.output_file_stderr)
        self.assertTrue(h.check())
        h.correct()

    def test_conv(self):
        self.assertEqual(len(get_conv(self.output_file_conv)), 45)


if __name__ == "__main__":
    unittest.main()
