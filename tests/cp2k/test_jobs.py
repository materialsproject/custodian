# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
import unittest
import warnings
from glob import glob
from pathlib import Path

from custodian import TEST_FILES, Custodian
from custodian.cp2k.jobs import Cp2kJob

MODULE_DIR = Path(__file__).resolve().parent
TEST_FILES_DIR = f"{TEST_FILES}/cp2k"

cwd = os.getcwd()


def clean_dir(dir):
    for f in glob(os.path.join(dir, "error.*.tar.gz")):
        os.remove(f)
    for f in glob(os.path.join(dir, "custodian.chk.*.tar.gz")):
        os.remove(f)


class HandlerTests(unittest.TestCase):
    def setUp(self):
        warnings.filterwarnings("ignore")

        clean_dir(TEST_FILES_DIR)

        self.input_file = f"{TEST_FILES_DIR}/cp2k.inp"
        self.input_file_hybrid = f"{TEST_FILES_DIR}/cp2k.inp.hybrid"
        self.output_file = f"{TEST_FILES_DIR}/cp2k.out.test"
        self.std_err = f"{TEST_FILES_DIR}/std_err.tmp"
        self.logfile = f"{TEST_FILES_DIR}/custodian.json"

        if os.path.isfile(Custodian.LOG_FILE):
            os.remove("custodian.json")
        if os.path.isfile(self.std_err):
            os.remove(self.std_err)
        if os.path.isfile(self.output_file):
            os.remove(self.output_file)

    def test_job(self):
        job = Cp2kJob(
            cp2k_cmd=["echo"],
            input_file=self.input_file,
            output_file=self.output_file,
            stderr_file=self.std_err,
            suffix="",
            final=True,
            backup=False,
            settings_override=None,
        )
        c = Custodian(jobs=[job], handlers=[])
        c.run()
        if os.path.isfile(Custodian.LOG_FILE):
            os.remove("custodian.json")
        if os.path.isfile(self.std_err):
            os.remove(self.std_err)

    def test_double(self):
        jobs = Cp2kJob.double_job(
            cp2k_cmd=["echo"],
            input_file=self.input_file_hybrid,
            output_file=self.output_file,
            stderr_file="std_err.tmp",
            backup=False,
        )
        assert len(jobs) == 2
