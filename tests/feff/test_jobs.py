import os
import subprocess

from monty.os import cd
from monty.tempfile import ScratchDir
from pymatgen.io.feff.inputs import Atoms, Tags

from custodian.feff.jobs import FeffJob
from tests.conftest import TEST_FILES

__author__ = "Chen Zheng"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Chen Zheng"
__email__ = "chz022@ucsd.edu"
__date__ = "Oct 18, 2017"

TEST_DIR = f"{TEST_FILES}/feff_unconverged"


def test_as_from_dict() -> None:
    f = FeffJob("hello")
    f2 = FeffJob.from_dict(f.as_dict())
    assert isinstance(f, FeffJob)
    assert f2.feff_cmd == "hello"


def test_setup(tmp_path) -> None:
    with cd(TEST_DIR), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
        f = FeffJob("hello", backup=True)
        f.setup()

        parameter = Tags.from_file("feff.inp")
        parameter_orig = Tags.from_file("feff.inp.orig")
        assert parameter == parameter_orig

        atom = Atoms.cluster_from_file("feff.inp")
        atom_origin = Atoms.cluster_from_file("feff.inp.orig")
        assert atom == atom_origin


def test_postprocess(tmp_path) -> None:
    with cd(TEST_DIR), ScratchDir(str(tmp_path), copy_from_current_on_enter=True):
        f = FeffJob("hello", backup=True, gzipped=True)
        f.postprocess()
        assert os.path.isfile("feff_out.1.tar.gz")
        f.postprocess()
        assert os.path.isfile("feff_out.2.tar.gz")


def test_run(tmp_path, monkeypatch) -> None:
    calls = []

    def mock_popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        kwargs["stdout"].write("stdout")
        kwargs["stderr"].write("stderr")
        return "proc"

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    job = FeffJob("feff8l", output_file="out.txt", stderr_file="err.txt")
    assert job.run(directory=str(tmp_path)) == "proc"
    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd == "feff8l"
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["shell"] is True
    assert kwargs["stdout"].name == os.path.join(str(tmp_path), "out.txt")
    assert kwargs["stdout"].closed
    assert kwargs["stderr"].closed
    assert (tmp_path / "out.txt").read_text() == "stdout"
    assert (tmp_path / "err.txt").read_text() == "stderr"


def test_postprocess_no_gzip(tmp_path) -> None:
    (tmp_path / "feff.out").write_text("done")
    FeffJob("hello", gzipped=False).postprocess(directory=str(tmp_path))
    assert not list(tmp_path.glob("*.tar.gz"))
