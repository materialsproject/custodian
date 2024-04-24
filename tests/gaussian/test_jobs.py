import glob
import gzip
import os
import shutil
from unittest import TestCase

from custodian.gaussian.jobs import GaussianJob
from tests.conftest import TEST_FILES

__author__ = "Rasha Atwi"
__version__ = "0.1"
__maintainer__ = "Rasha Atwi"
__email__ = "rasha.atwi@stonybrook.edu"
__status__ = "Alpha"
__date__ = "3/21/24"

TEST_DIR = f"{TEST_FILES}/gaussian"
SCR_DIR = f"{TEST_DIR}/scratch"
CWD = os.getcwd()


class TestGaussianJob(TestCase):
    def setUp(self):
        self.input_file = "test.com"
        self.output_file = "test.out"
        self.gaussian_cmd = f"g16 < {self.input_file} > {self.output_file}"
        self.stderr_file = "stderr.txt"
        self.suffix = ".test"
        self.backup = True
        self.directory = SCR_DIR

        os.makedirs(SCR_DIR, exist_ok=True)
        shutil.copyfile(f"{TEST_DIR}/mol_opt.com", f"{SCR_DIR}/test.com")
        os.chdir(SCR_DIR)

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)
        files_to_remove = glob.glob(f"{TEST_DIR}/*.out")
        if files_to_remove and glob.glob(f"{TEST_DIR}/*.out.gz"):
            for file_path in files_to_remove:
                os.remove(file_path)

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
        assert os.path.exists(f"{SCR_DIR}/test.com.orig")
        if not os.path.exists(f"{TEST_DIR}/mol_opt.out") and os.path.exists(f"{TEST_DIR}/mol_opt.out.gz"):
            with gzip.open(f"{TEST_DIR}/mol_opt.out.gz", "rb") as f_in, open(f"{TEST_DIR}/mol_opt.out", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        shutil.copy(f"{TEST_DIR}/mol_opt.out", f"{SCR_DIR}/test.out")
        job.postprocess()
        assert os.path.exists(f"{SCR_DIR}/test.com{self.suffix}")
        assert os.path.exists(f"{SCR_DIR}/test.out{self.suffix}")

    def test_better_guess(self):
        job_gen = GaussianJob.generate_better_guess(
            self.gaussian_cmd,
            self.input_file,
            self.output_file,
            self.stderr_file,
            self.backup,
            True,
            self.directory,
        )
        jobs = list(job_gen)
        assert len(jobs) == 1, "One job should be generated under normal conditions."
        jobs[0].setup()
        assert os.path.exists(f"{SCR_DIR}/test.com.orig")
        if not os.path.exists(f"{TEST_DIR}/mol_opt.out") and os.path.exists(f"{TEST_DIR}/mol_opt.out.gz"):
            with gzip.open(f"{TEST_DIR}/mol_opt.out.gz", "rb") as f_in, open(f"{TEST_DIR}/mol_opt.out", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        shutil.copy(f"{TEST_DIR}/mol_opt.out", f"{SCR_DIR}/test.out")
        jobs[0].postprocess()
        assert os.path.exists(f"{SCR_DIR}/test.com.guess1")
        assert os.path.exists(f"{SCR_DIR}/test.out.guess1")
