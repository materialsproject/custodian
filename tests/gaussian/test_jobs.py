import gzip
import os
import shutil
import subprocess
from unittest import TestCase
from unittest.mock import MagicMock

import pytest
from pymatgen.io.gaussian import GaussianInput

from custodian.gaussian.handlers import GaussianErrorHandler
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


def copy_gz(src: str, dst) -> None:
    with gzip.open(src, "rb") as f_in, open(dst, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


@pytest.fixture
def job_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(GaussianErrorHandler, "activate_better_guess", False)
    shutil.copyfile(f"{TEST_DIR}/mol_opt.com", tmp_path / "test.com")
    return tmp_path


def test_run_and_terminate(job_dir, monkeypatch):
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    job = GaussianJob("g16 < test.com", "test.com", "test.out", stderr_file="err.txt")
    # terminate before run is a no-op
    job.terminate()

    process = job.run(directory=str(job_dir))

    assert process is mock_popen.return_value
    assert job.process is process
    args, kwargs = mock_popen.call_args
    assert args == ("g16 < test.com",)
    assert kwargs["shell"] is True
    assert kwargs["cwd"] == str(job_dir)
    assert kwargs["stdout"].name == os.path.join(str(job_dir), "test.out")
    assert kwargs["stderr"].name == os.path.join(str(job_dir), "err.txt")
    assert (job_dir / "test.out").exists()
    assert (job_dir / "err.txt").exists()

    job.terminate()
    process.terminate.assert_called_once_with()


def test_setup_no_backup(job_dir):
    job = GaussianJob("g16", "test.com", "test.out", backup=False)
    job.setup()
    assert not (job_dir / "test.com.orig").exists()


def test_postprocess_no_suffix(job_dir):
    job = GaussianJob("g16", "test.com", "test.out", suffix="")
    job.postprocess()
    assert sorted(os.listdir(job_dir)) == ["test.com"]


def test_better_guess_second_job(job_dir):
    copy_gz(f"{TEST_DIR}/mol_opt.out.gz", job_dir / "test.out")
    shutil.copyfile(f"{TEST_DIR}/Optimization.chk", job_dir / "Optimization.chk")
    job_gen = GaussianJob.generate_better_guess("g16", "test.com", "test.out", directory=str(job_dir))
    first = next(job_gen)
    assert first.suffix == ".guess1"

    # the handler switched to a lower level of theory and the lower job succeeded
    GaussianErrorHandler.activate_better_guess = True
    second = next(job_gen)
    assert second.suffix == ".guess2"
    assert second.input_file == "test.com"
    with pytest.raises(StopIteration):
        next(job_gen)

    gin = GaussianInput.from_file(job_dir / "test.com")
    assert gin.route_parameters["Guess"] == "Read"
    assert gin.route_parameters["Geom"] == "Checkpoint"
    # geometry is read from the checkpoint, so no atoms are written
    assert len(gin.molecule) == 0
    assert gin.functional == "B3LYP"
    assert gin.basis_set == "6-31+G*"


def test_better_guess_lower_job_failed(job_dir):
    copy_gz(f"{TEST_DIR}/opt_steps_cycles.out.gz", job_dir / "test.out")
    job_gen = GaussianJob.generate_better_guess("g16", "test.com", "test.out", directory=str(job_dir))
    next(job_gen)
    GaussianErrorHandler.activate_better_guess = True
    with pytest.raises(StopIteration):
        next(job_gen)
    # input is untouched
    with open(job_dir / "test.com") as f1, open(f"{TEST_DIR}/mol_opt.com") as f2:
        assert f1.read() == f2.read()


def test_better_guess_missing_chk(job_dir):
    copy_gz(f"{TEST_DIR}/mol_opt.out.gz", job_dir / "test.out")
    job_gen = GaussianJob.generate_better_guess("g16", "test.com", "test.out", directory=str(job_dir))
    next(job_gen)
    GaussianErrorHandler.activate_better_guess = True
    with pytest.raises(FileNotFoundError, match="checkpoint"):
        next(job_gen)


def test_better_guess_finds_chk_in_directory(tmp_path, monkeypatch):
    (run_dir := tmp_path / "run").mkdir()
    (cwd := tmp_path / "cwd").mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(GaussianErrorHandler, "activate_better_guess", False)
    shutil.copyfile(f"{TEST_DIR}/mol_opt.com", run_dir / "test.com")
    copy_gz(f"{TEST_DIR}/mol_opt.out.gz", run_dir / "test.out")
    shutil.copyfile(f"{TEST_DIR}/Optimization.chk", run_dir / "Optimization.chk")
    job_gen = GaussianJob.generate_better_guess("g16", "test.com", "test.out", directory=str(run_dir))
    next(job_gen)
    GaussianErrorHandler.activate_better_guess = True
    assert next(job_gen).suffix == ".guess2"
