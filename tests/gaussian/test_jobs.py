import gzip
import os
import shutil
from unittest import TestCase

import pytest

from custodian.gaussian.jobs import GaussianJob
from tests.conftest import TEST_FILES

__author__ = "Rasha Atwi"
__version__ = "0.1"
__maintainer__ = "Rasha Atwi"
__email__ = "rasha.atwi@stonybrook.edu"
__status__ = "Alpha"
__date__ = "3/21/24"

TEST_DIR = f"{TEST_FILES}/gaussian"


class TestGaussianJob(TestCase):
    @pytest.fixture(autouse=True)
    def _run_in_tmp_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.scr_dir = str(tmp_path)

    def setUp(self):
        self.input_file = "test.com"
        self.output_file = "test.out"
        self.gaussian_cmd = f"g16 < {self.input_file} > {self.output_file}"
        self.stderr_file = "stderr.txt"
        self.suffix = ".test"
        self.backup = True
        self.directory = self.scr_dir
        shutil.copyfile(f"{TEST_DIR}/mol_opt.com", f"{self.scr_dir}/test.com")

    def test_normal(self):
        job = GaussianJob(
            self.gaussian_cmd,
            self.input_file,
            self.output_file,
            self.stderr_file,
            self.suffix,
            self.backup,
        )
        job.setup()
        assert os.path.exists(f"{self.scr_dir}/test.com.orig")
        with gzip.open(f"{TEST_DIR}/mol_opt.out.gz", "rb") as f_in, open(f"{self.scr_dir}/test.out", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        job.postprocess()
        assert os.path.exists(f"{self.scr_dir}/test.com{self.suffix}")
        assert os.path.exists(f"{self.scr_dir}/test.out{self.suffix}")

    def test_better_guess(self):
        job_gen = GaussianJob.generate_better_guess(
            self.gaussian_cmd,
            self.input_file,
            self.output_file,
            self.stderr_file,
            self.backup,
            cart_coords=True,
            directory=self.directory,
        )
        jobs = list(job_gen)
        assert len(jobs) == 1, "One job should be generated under normal conditions."
        jobs[0].setup()
        assert os.path.exists(f"{self.scr_dir}/test.com.orig")
        with gzip.open(f"{TEST_DIR}/mol_opt.out.gz", "rb") as f_in, open(f"{self.scr_dir}/test.out", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        jobs[0].postprocess()
        assert os.path.exists(f"{self.scr_dir}/test.com.guess1")
        assert os.path.exists(f"{self.scr_dir}/test.out.guess1")
