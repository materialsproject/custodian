import gzip
import shutil
import subprocess
from pathlib import Path

import pytest

from custodian.nwchem.jobs import NwchemJob
from tests.conftest import TEST_FILES

NWCHEM_FILES = f"{TEST_FILES}/nwchem"
INPUT = "Li1_1.nw"


@pytest.fixture
def run_dir(tmp_path, monkeypatch) -> Path:
    """Isolated run directory containing a copy of an NWChem input; cwd set to it."""
    shutil.copy(f"{NWCHEM_FILES}/{INPUT}", tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_popen(monkeypatch) -> list[dict]:
    """Replace subprocess.Popen with a recorder; returns the list of recorded calls."""
    calls: list[dict] = []

    def fake_popen(args, **kwargs):
        kwargs["stdout"].write("fake nwchem output\n")
        calls.append({"args": args, **kwargs})
        return "fake-process"

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    return calls


def test_init_defaults() -> None:
    job = NwchemJob(["nwchem"])
    assert job.nwchem_cmd == ["nwchem"]
    assert job.input_file == "mol.nw"
    assert job.output_file == "mol.nwout"
    assert job.backup is True
    assert job.gzipped is False
    assert job.settings_override is None


def test_as_from_dict() -> None:
    job = NwchemJob(["mpirun", "nwchem"], input_file=INPUT, output_file="out.nwout", gzipped=True, backup=False)
    job2 = NwchemJob.from_dict(job.as_dict())
    assert isinstance(job2, NwchemJob)
    assert job2.nwchem_cmd == ["mpirun", "nwchem"]
    assert job2.input_file == INPUT
    assert job2.output_file == "out.nwout"
    assert job2.gzipped is True
    assert job2.backup is False


@pytest.mark.parametrize("backup", [True, False])
def test_setup_backup(run_dir, backup) -> None:
    NwchemJob(["nwchem"], input_file=INPUT, backup=backup).setup()
    orig = run_dir / f"{INPUT}.orig"
    assert orig.exists() is backup
    if backup:
        assert orig.read_text() == (run_dir / INPUT).read_text()


def test_setup_backup_with_directory(tmp_path, monkeypatch) -> None:
    run = tmp_path / "run"
    run.mkdir()
    shutil.copy(f"{NWCHEM_FILES}/{INPUT}", run)
    monkeypatch.chdir(tmp_path)
    NwchemJob(["nwchem"], input_file=INPUT).setup(directory=str(run))
    assert (run / f"{INPUT}.orig").read_text() == (run / INPUT).read_text()
    assert not (tmp_path / f"{INPUT}.orig").exists()


def test_run_opens_output_in_text_mode(run_dir, monkeypatch) -> None:
    """Regression: zopen(output_file, "w") without t/b raised RuntimeError under current monty."""
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: None)
    NwchemJob(["nwchem"], input_file=INPUT).run()
    assert (run_dir / "mol.nwout").exists()


def test_run_constructs_command(run_dir, mock_popen) -> None:
    job = NwchemJob(["mpirun", "-np", "4", "nwchem"], input_file=INPUT, output_file="Li1_1.nwout")
    proc = job.run()
    assert proc == "fake-process"
    assert len(mock_popen) == 1
    call = mock_popen[0]
    assert call["args"] == ["mpirun", "-np", "4", "nwchem", INPUT]
    assert call["cwd"] == "./"
    # stdout is redirected to the output file, which is closed after launching.
    assert call["stdout"].closed
    assert (run_dir / "Li1_1.nwout").read_text() == "fake nwchem output\n"


def test_run_passes_directory_as_cwd(run_dir, mock_popen) -> None:
    NwchemJob(["nwchem"], input_file=INPUT).run(directory=str(run_dir))
    assert mock_popen[0]["cwd"] == str(run_dir)


def test_run_writes_output_into_directory(tmp_path, monkeypatch, mock_popen) -> None:
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.chdir(tmp_path)
    NwchemJob(["nwchem"], input_file=INPUT).run(directory=str(run))
    assert (run / "mol.nwout").exists()


def test_postprocess_gzipped(run_dir) -> None:
    (run_dir / "mol.nwout").write_text("output\n")
    NwchemJob(["nwchem"], input_file=INPUT, gzipped=True).postprocess()
    assert sorted(p.name for p in run_dir.iterdir()) == [f"{INPUT}.gz", "mol.nwout.gz"]
    with gzip.open(run_dir / "mol.nwout.gz", "rt") as file:
        assert file.read() == "output\n"


def test_postprocess_gzipped_with_directory(tmp_path, monkeypatch) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "mol.nwout").write_text("output\n")
    (tmp_path / "untouched.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    NwchemJob(["nwchem"], gzipped=True).postprocess(directory=str(run))
    assert [p.name for p in run.iterdir()] == ["mol.nwout.gz"]
    assert (tmp_path / "untouched.txt").exists()


def test_postprocess_not_gzipped(run_dir) -> None:
    (run_dir / "mol.nwout").write_text("output\n")
    NwchemJob(["nwchem"], input_file=INPUT).postprocess()
    assert sorted(p.name for p in run_dir.iterdir()) == [INPUT, "mol.nwout"]
