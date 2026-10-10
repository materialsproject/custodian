# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import shutil
import tempfile
import unittest
import warnings
from pathlib import Path

from custodian.cp2k.jobs import Cp2kJob
from custodian.custodian import Custodian
from tests.conftest import TEST_FILES

MODULE_DIR = Path(__file__).resolve().parent
TEST_FILES_DIR = f"{TEST_FILES}/cp2k"


class HandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore")

        self.input_file = f"{TEST_FILES_DIR}/cp2k.inp"
        self.input_file_hybrid = f"{TEST_FILES_DIR}/cp2k.inp.hybrid"
        self.output_file = f"{TEST_FILES_DIR}/cp2k.out.test"

    def test_job(self) -> None:
        # Run in an isolated directory: Cp2kJob.setup decompresses everything under the run directory.
        with tempfile.TemporaryDirectory() as tmp_dir:
            shutil.copy(self.input_file, tmp_dir)
            job = Cp2kJob(
                cp2k_cmd=["echo"],
                input_file="cp2k.inp",
                output_file="cp2k.out.test",
                stderr_file="std_err.tmp",
                suffix="",
                final=True,
                backup=False,
                settings_override=None,
            )
            c = Custodian(jobs=[job], handlers=[], directory=tmp_dir)
            c.run()

    def test_double(self) -> None:
        jobs = Cp2kJob.double_job(
            cp2k_cmd=["echo"],
            input_file=self.input_file_hybrid,
            output_file=self.output_file,
            stderr_file="std_err.tmp",
            backup=False,
        )
        assert len(jobs) == 2
