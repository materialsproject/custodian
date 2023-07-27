# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import glob
import os
import shutil
import time
import unittest
import warnings
from pathlib import Path

from pymatgen.io.cp2k.inputs import Keyword, KeywordList
from pymatgen.io.cp2k.sets import StaticSet

from custodian.cp2k.handlers import (
    AbortHandler,
    FrozenJobErrorHandler,
    NumericalPrecisionHandler,
    StdErrHandler,
    UnconvergedScfErrorHandler,
    get_conv,
)
from custodian.cp2k.interpreter import Cp2kModder


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

        self.input_file = os.path.join(self.TEST_FILES_DIR, "cp2k.inp")

        self.output_file_preconditioner = os.path.join(self.TEST_FILES_DIR, "cp2k.out.precondstuck")
        self.output_file_choleesky = os.path.join(self.TEST_FILES_DIR, "cp2k.out.cholesky")
        self.output_file_imprecise = os.path.join(self.TEST_FILES_DIR, "cp2k.out.imprecise")
        self.output_file_unconverged = os.path.join(self.TEST_FILES_DIR, "cp2k.out.unconverged")
        self.output_file_stderr = os.path.join(self.TEST_FILES_DIR, "std_err.txt")
        self.output_file_hybrid = os.path.join(self.TEST_FILES_DIR, "cp2k.out.hybrid")
        self.output_file_conv = os.path.join(self.TEST_FILES_DIR, "cp2k.out.conv")

        self.modder = Cp2kModder(filename=self.input_file)

    def test(self):
        """Ensure modder works"""
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
        assert self.modder.ci["FORCE_EVAL"]["METHOD"] == Keyword("METHOD", "NOT QA")
        assert isinstance(self.modder.ci["FORCE_EVAL"]["DFT"]["BASIS_SET_FILE_NAME"], KeywordList)

    def test_handler_inits(self):
        """Ensure handlers initialize fine without real input/output files"""
        for handler in [AbortHandler, FrozenJobErrorHandler, NumericalPrecisionHandler, UnconvergedScfErrorHandler]:
            handler()

    def test_frozenjobhandler(self):
        """Handler for frozen job"""
        h = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_preconditioner, timeout=1)
        assert h.check()
        ci = StaticSet.from_file(self.input_file)
        assert ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECONDITIONER"] == Keyword(
            "PRECONDITIONER", "FULL_SINGLE_INVERSE"
        )
        h.correct()

        ci = StaticSet.from_file(self.input_file)
        assert ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECONDITIONER"] == Keyword("PRECONDITIONER", "FULL_ALL")

        h = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_preconditioner, timeout=1)
        assert h.check()
        h.correct()
        ci = StaticSet.from_file(self.input_file)
        assert ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECOND_SOLVER"] == Keyword("PRECOND_SOLVER", "DIRECT")

        h = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_imprecise, timeout=1)
        h.check()

    def test_uncoverge_handler(self):
        """Handler for SCF handling not working"""
        ci = StaticSet.from_file(self.input_file)
        h = UnconvergedScfErrorHandler(input_file=self.input_file, output_file=self.output_file_unconverged)
        h.check()
        assert h.is_ot
        assert ci["force_eval"]["dft"]["scf"]["ot"]["minimizer"] == Keyword("MINIMIZER", "DIIS")
        actions = h.correct()
        assert actions["errors"], ["Non-converging Job"]
        ci = StaticSet.from_file(self.input_file)
        assert ci["force_eval"]["dft"]["scf"]["ot"]["minimizer"] == Keyword("MINIMIZER", "CG")

        # Fake diag check. Turns on mixing
        h.is_ot = False
        actions = h.correct()
        assert actions["errors"], ["Non-converging Job"]
        ci = StaticSet.from_file(self.input_file)
        assert ci["force_eval"]["dft"]["scf"]["MIXING"]["ALPHA"] == Keyword("ALPHA", 0.1)

    def test_abort_handler(self):
        """Checks if cp2k called abort"""
        h = AbortHandler(input_file=self.input_file, output_file=self.output_file_choleesky)
        assert h.check()

    def test_imprecision_handler(self):
        """Check for low precision leading to stagnant SCF"""
        h = NumericalPrecisionHandler(self.input_file, output_file=self.output_file_imprecise, max_same=3)
        assert h.check()
        c = h.correct()
        assert c["errors"], ["Unsufficient precision"]

    def test_std_out(self):
        """Errors sent to the std out instead of cp2k out"""
        h = StdErrHandler(std_err=self.output_file_stderr)
        assert h.check()
        h.correct()

    def test_conv(self):
        """Check that SCF convergence can be read"""
        assert len(get_conv(self.output_file_conv)) == 45


if __name__ == "__main__":
    unittest.main()
