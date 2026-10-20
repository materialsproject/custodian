# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import gzip
import os
import shutil
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path

import pytest
from pymatgen.io.cp2k.inputs import Cp2kInput

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


# ---------------------------------------------------------------------------
# pytest-style tests: setup/run/postprocess/terminate without executing CP2K.


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    shutil.copy(f"{TEST_FILES_DIR}/cp2k.inp.orig", tmp_path / "cp2k.inp")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_type(path) -> str:
    return Cp2kInput.from_file(path)["GLOBAL"]["RUN_TYPE"].values[0]


def test_setup_backup_only(run_dir) -> None:
    job = Cp2kJob(cp2k_cmd=["cp2k.popt"])
    job.setup()
    assert job.ci.check("FORCE_EVAL/DFT/SCF/OT")
    assert (run_dir / "cp2k.inp.orig").read_text() == (run_dir / "cp2k.inp").read_text()


def test_setup_no_backup(run_dir) -> None:
    Cp2kJob(cp2k_cmd=["cp2k.popt"], backup=False).setup()
    assert not (run_dir / "cp2k.inp.orig").exists()


def test_setup_decompresses_input(run_dir) -> None:
    with open(run_dir / "cp2k.inp", "rb") as f_in, gzip.open(run_dir / "cp2k.inp.gz", "wb") as f_out:
        f_out.write(f_in.read())
    (run_dir / "cp2k.inp").unlink()
    job = Cp2kJob(cp2k_cmd=["cp2k.popt"], backup=False)
    job.setup(directory=str(run_dir))
    assert job.ci.check("FORCE_EVAL/DFT/SCF/OT")
    assert (run_dir / "cp2k.inp").exists()
    assert not (run_dir / "cp2k.inp.gz").exists()


def test_setup_settings_override(run_dir) -> None:
    override = [{"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"RUN_TYPE": "ENERGY"}}}}]
    Cp2kJob(cp2k_cmd=["cp2k.popt"], settings_override=override).setup(directory=str(run_dir))
    assert run_type(run_dir / "cp2k.inp") == "ENERGY"
    # The backup is taken after the overrides are applied.
    assert run_type(run_dir / "cp2k.inp.orig") == "ENERGY"


def test_setup_restart_copies_restart_file(run_dir) -> None:
    ci = Cp2kInput.from_file(run_dir / "cp2k.inp")
    ci.update({"GLOBAL": {"PROJECT_NAME": "RESTARTED"}})
    ci.write_file(run_dir / "CP2K-1.restart")
    (run_dir / "cp2k.out").write_text(" PROGRAM ENDED AT  2020-08-28\n")

    override = [{"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"RUN_TYPE": "GEO_OPT"}}}}]
    job = Cp2kJob(cp2k_cmd=["cp2k.popt"], restart=True, backup=False, settings_override=override)
    job.setup()

    assert "file" in job.settings_override[0]
    new = Cp2kInput.from_file(run_dir / "cp2k.inp")
    assert new["GLOBAL"]["PROJECT_NAME"].values[0] == "RESTARTED"
    assert new["GLOBAL"]["RUN_TYPE"].values[0] == "GEO_OPT"


def test_setup_relative_directory(tmp_path, monkeypatch) -> None:
    (tmp_path / "run").mkdir()
    shutil.copy(f"{TEST_FILES_DIR}/cp2k.inp.orig", tmp_path / "run" / "cp2k.inp")
    monkeypatch.chdir(tmp_path)
    override = [{"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"RUN_TYPE": "ENERGY"}}}}]
    Cp2kJob(cp2k_cmd=["cp2k.popt"], settings_override=override, backup=False).setup(directory="run")
    assert run_type(tmp_path / "run" / "cp2k.inp") == "ENERGY"
    assert not (tmp_path / "run" / "run").exists()


def test_run_launches_popen(run_dir, monkeypatch) -> None:
    calls = {}

    def fake_popen(cmd, **kwargs):
        calls["cmd"] = cmd
        calls.update(kwargs)
        return "proc"

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    job = Cp2kJob(cp2k_cmd=["mpirun", "cp2k.popt"], output_file="out.log", stderr_file="err.log")
    assert job.run(directory=str(run_dir)) == "proc"
    assert calls["cmd"] == ["mpirun", "cp2k.popt", "-i", "cp2k.inp"]
    assert calls["cwd"] == str(run_dir)
    assert calls["shell"] is False
    assert calls["stdout"].name == os.path.join(str(run_dir), "out.log")
    assert calls["stderr"].name == os.path.join(str(run_dir), "err.log")
    # cp2k_cmd itself must not be mutated.
    assert job.cp2k_cmd == ["mpirun", "cp2k.popt"]


@pytest.fixture
def finished_dir(run_dir):
    (run_dir / "cp2k.out").write_text("done\n")
    (run_dir / "custodian.json").write_text("[]")
    (run_dir / "continue.json").write_text("{}")
    (run_dir / "subdir").mkdir()
    return run_dir


@pytest.mark.parametrize("final", [True, False])
def test_postprocess_with_suffix(finished_dir, final) -> None:
    Cp2kJob(cp2k_cmd=["cp2k.popt"], suffix=".1", final=final).postprocess()
    archive = finished_dir / "run.1"
    assert sorted(p.name for p in archive.iterdir()) == ["cp2k.inp", "cp2k.out"]
    # final jobs move files into the archive; intermediate jobs copy them.
    assert (finished_dir / "cp2k.out").exists() is not final
    assert (finished_dir / "cp2k.inp").exists() is not final
    assert (finished_dir / "custodian.json").exists()
    assert (finished_dir / "subdir").is_dir()
    assert not (finished_dir / "continue.json").exists()


def test_postprocess_without_suffix(finished_dir) -> None:
    Cp2kJob(cp2k_cmd=["cp2k.popt"]).postprocess()
    assert not any(p.name.startswith("run") for p in finished_dir.iterdir())
    assert (finished_dir / "cp2k.out").exists()
    assert not (finished_dir / "continue.json").exists()


def test_postprocess_in_other_directory(tmp_path, monkeypatch) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "cp2k.out").write_text("done\n")
    monkeypatch.chdir(tmp_path)
    Cp2kJob(cp2k_cmd=["cp2k.popt"], suffix=".1").postprocess(directory=str(run))
    assert (run / "run.1" / "cp2k.out").exists()
    assert not (tmp_path / "run.1").exists()


def test_terminate(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(os, "system", calls.append)
    Cp2kJob(cp2k_cmd=["mpirun", "-np", "4", "cp2k.psmp"]).terminate()
    assert calls == ["killall cp2k.psmp"]


def test_terminate_swallows_errors(monkeypatch) -> None:
    def boom(cmd):
        raise OSError(cmd)

    monkeypatch.setattr(os, "system", boom)
    Cp2kJob(cp2k_cmd=["cp2k.popt"]).terminate()


@pytest.mark.parametrize(
    ("factory", "inp", "n_jobs"),
    [
        (Cp2kJob.gga_static_to_hybrid, "cp2k.inp.orig", 2),  # RUN_TYPE DEBUG
        (Cp2kJob.gga_static_to_hybrid, "cp2k.inp.hybrid", 1),  # RUN_TYPE ENERGY_FORCE
        (Cp2kJob.pre_screen_hybrid, "cp2k.inp.orig", 2),
        (Cp2kJob.pre_screen_hybrid, "cp2k.inp.hybrid", 1),
        (Cp2kJob.double_job, "cp2k.inp.orig", 2),
        (Cp2kJob.double_job, "cp2k.inp.hybrid", 2),
    ],
)
def test_multi_job_factories(tmp_path, factory, inp, n_jobs) -> None:
    shutil.copy(f"{TEST_FILES_DIR}/{inp}", tmp_path / "cp2k.inp")
    jobs = factory(cp2k_cmd=["cp2k.popt"], directory=str(tmp_path))
    assert len(jobs) == n_jobs
    assert jobs[0].suffix == "1"
    assert not jobs[0].final
    if n_jobs == 2:
        assert jobs[1].suffix == "2"
        assert jobs[1].final
        # The second job restores the original run type.
        assert jobs[1].settings_override[0]["action"]["_set"]["GLOBAL"]["RUN_TYPE"] == run_type(tmp_path / "cp2k.inp")
    if factory is Cp2kJob.double_job:
        assert jobs[1].restart
        # The first job is forced to a single point unless it is already an energy-only run.
        assert jobs[0].settings_override[0]["action"]["_set"]["GLOBAL"]["RUN_TYPE"] == "ENERGY_FORCE"
