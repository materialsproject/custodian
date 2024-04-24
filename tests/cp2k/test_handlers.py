# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
import shutil
import time
import unittest
import warnings
from glob import glob

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
from tests.conftest import TEST_FILES

TEST_FILES_DIR = f"{TEST_FILES}/cp2k"


def clean_dir(dct) -> None:
    for file in glob(os.path.join(dct, "error.*.tar.gz")):
        os.remove(file)
    for file in glob(os.path.join(dct, "custodian.chk.*.tar.gz")):
        os.remove(file)


class HandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore")

        clean_dir(TEST_FILES_DIR)

        time.sleep(1)  # for frozenhandler

        shutil.copy(f"{TEST_FILES_DIR}/cp2k.inp.orig", f"{TEST_FILES_DIR}/cp2k.inp")

        self.input_file = f"{TEST_FILES_DIR}/cp2k.inp"

        self.output_file_preconditioner = f"{TEST_FILES_DIR}/cp2k.out.precondstuck"
        self.output_file_cholesky = f"{TEST_FILES_DIR}/cp2k.out.cholesky"
        self.output_file_imprecise = f"{TEST_FILES_DIR}/cp2k.out.imprecise"
        self.output_file_unconverged = f"{TEST_FILES_DIR}/cp2k.out.unconverged"
        self.output_file_stderr = f"{TEST_FILES_DIR}/std_err.txt"
        self.output_file_hybrid = f"{TEST_FILES_DIR}/cp2k.out.hybrid"
        self.output_file_conv = f"{TEST_FILES_DIR}/cp2k.out.conv"

        self.modder = Cp2kModder(filename=self.input_file)

    def test(self) -> None:
        """Ensure modder works"""
        kwds = KeywordList(keywords=[Keyword("BASIS_SET_FILE_NAME", "FILE1"), Keyword("BASIS_SET_FILE_NAME", "FILE2")])
        actions = [
            {"dict": self.input_file, "action": {"_set": {"FORCE_EVAL": {"METHOD": "NOT QA"}}}},
            {"dict": self.input_file, "action": {"_set": {"FORCE_EVAL": {"DFT": {"BASIS_SET_FILE_NAME": kwds}}}}},
            {
                "dict": self.input_file,
                "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MAX_SCF": 50}, "OUTER_SCF": {"MAX_SCF": 8}}}}},
            },
        ]
        self.modder.apply_actions(actions=actions)
        assert self.modder.ci["FORCE_EVAL"]["METHOD"] == Keyword("METHOD", "NOT QA")
        assert isinstance(self.modder.ci["FORCE_EVAL"]["DFT"]["BASIS_SET_FILE_NAME"], KeywordList)

    def test_handler_inits(self) -> None:
        """Ensure handlers initialize fine without real input/output files"""
        for handler in (AbortHandler, FrozenJobErrorHandler, NumericalPrecisionHandler, UnconvergedScfErrorHandler):
            handler()

    def test_frozenjobhandler(self) -> None:
        """Handler for frozen job"""
        handler = FrozenJobErrorHandler(
            input_file=self.input_file, output_file=self.output_file_preconditioner, timeout=1
        )
        assert handler.check()
        ci = StaticSet.from_file(self.input_file)
        assert ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECONDITIONER"] == Keyword(
            "PRECONDITIONER", "FULL_SINGLE_INVERSE"
        )
        handler.correct()

        ci = StaticSet.from_file(self.input_file)
        assert ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECONDITIONER"] == Keyword("PRECONDITIONER", "FULL_ALL")

        handler = FrozenJobErrorHandler(
            input_file=self.input_file, output_file=self.output_file_preconditioner, timeout=1
        )
        assert handler.check()
        handler.correct()
        ci = StaticSet.from_file(self.input_file)
        assert ci["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["PRECOND_SOLVER"] == Keyword("PRECOND_SOLVER", "DIRECT")

        handler = FrozenJobErrorHandler(input_file=self.input_file, output_file=self.output_file_imprecise, timeout=1)
        handler.check()

    def test_unconverged_handler(self) -> None:
        """Handler for SCF handling not working"""
        ci = StaticSet.from_file(self.input_file)
        handler = UnconvergedScfErrorHandler(input_file=self.input_file, output_file=self.output_file_unconverged)
        handler.check()
        assert handler.is_ot
        assert ci["force_eval"]["dft"]["scf"]["ot"]["minimizer"] == Keyword("MINIMIZER", "DIIS")
        actions = handler.correct()
        assert actions["errors"], ["Non-converging Job"]
        ci = StaticSet.from_file(self.input_file)
        assert ci["force_eval"]["dft"]["scf"]["ot"]["minimizer"] == Keyword("MINIMIZER", "CG")

        # Fake diag check. Turns on mixing
        handler.is_ot = False
        actions = handler.correct()
        assert actions["errors"], ["Non-converging Job"]
        ci = StaticSet.from_file(self.input_file)
        assert ci["force_eval"]["dft"]["scf"]["MIXING"]["ALPHA"] == Keyword("ALPHA", 0.1)

    def test_abort_handler(self) -> None:
        """Checks if cp2k called abort"""
        handler = AbortHandler(input_file=self.input_file, output_file=self.output_file_cholesky)
        assert handler.check()

    def test_imprecision_handler(self) -> None:
        """Check for low precision leading to stagnant SCF"""
        handler = NumericalPrecisionHandler(self.input_file, output_file=self.output_file_imprecise, max_same=3)
        assert handler.check()
        c = handler.correct()
        assert c["errors"], ["Insufficient precision"]

    def test_std_out(self) -> None:
        """Errors sent to the std out instead of cp2k out"""
        handler = StdErrHandler(std_err=self.output_file_stderr)
        assert handler.check()
        handler.correct()

    def test_conv(self) -> None:
        """Check that SCF convergence can be read"""
        assert len(get_conv(self.output_file_conv)) == 45
