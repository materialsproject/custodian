import os
import shutil
from glob import glob
from pathlib import Path

import pytest
from pymatgen.io.nwchem import NwInput

from custodian.nwchem.handlers import NwchemErrorHandler
from tests.conftest import TEST_FILES

__author__ = "shyuepingong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "6/18/13"


def test_check_correct(tmp_path, monkeypatch) -> None:
    shutil.copytree(f"{TEST_FILES}/nwchem", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    shutil.copy("C1N1Cl1_1.nw", "C1N1Cl1_1.nw.orig")
    handler = NwchemErrorHandler(output_filename="C1N1Cl1_1.nwout")
    handler.check()
    handler.correct()
    shutil.move("C1N1Cl1_1.nw.orig", "C1N1Cl1_1.nw")
    shutil.copy("Li1_1.nw", "Li1_1.nw.orig")
    handler = NwchemErrorHandler(output_filename="Li1_1.nwout")
    handler.check()
    handler.correct()
    shutil.move("Li1_1.nw.orig", "Li1_1.nw")
    for file in glob("error.*.tar.gz"):
        os.remove(file)


@pytest.fixture
def nwchem_dir(tmp_path, monkeypatch):
    shutil.copytree(f"{TEST_FILES}/nwchem", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("output", "expected_errors", "ntasks"),
    [("C1N1Cl1_1.nwout", ["autoz error"], 1), ("Li1_1.nwout", ["Bad convergence"], 3)],
)
def test_check(nwchem_dir, output, expected_errors, ntasks) -> None:
    handler = NwchemErrorHandler(output_filename=output)
    assert handler.check() is True
    assert handler.errors == expected_errors
    assert handler.ntasks == ntasks
    assert handler.input_file == output.replace(".nwout", ".nw")


def test_correct_autoz(nwchem_dir) -> None:
    handler = NwchemErrorHandler(output_filename="C1N1Cl1_1.nwout")
    handler.check()
    result = handler.correct()
    assert result["errors"] == ["autoz error"]
    assert result["actions"] == [{"_set": {"geometry_options": ["units", "angstroms", "noautoz"]}}]
    assert NwInput.from_file("C1N1Cl1_1.nw").geometry_options == ["units", "angstroms", "noautoz"]
    assert glob("error.*.tar.gz")


def test_correct_bad_convergence_adds_then_pops_cgmin(nwchem_dir) -> None:
    # C1N1Cl1_1.nw has tasks [optimize, freq, energy, energy, energy]; pretend the first task failed.
    handler = NwchemErrorHandler(output_filename="C1N1Cl1_1.nwout")
    handler.check()
    handler.errors = ["Bad convergence"]
    handler.ntasks = 1

    handler.correct()
    tasks = NwInput.from_file("C1N1Cl1_1.nw").tasks
    assert len(tasks) == 5
    assert "cgmin" in tasks[0].theory_directives
    # Hessians cannot be computed with cgmin, so freq tasks get nocgmin.
    assert tasks[1].operation == "freq"
    assert "nocgmin" in tasks[1].theory_directives
    assert all("nocgmin" not in t.theory_directives for t in tasks if not t.operation.startswith("freq"))

    # cgmin already tried for the failed task: the task is dropped.
    handler.correct()
    tasks = NwInput.from_file("C1N1Cl1_1.nw").tasks
    assert len(tasks) == 4
    assert tasks[0].operation == "freq"


def test_correct_unknown_error(nwchem_dir) -> None:
    handler = NwchemErrorHandler(output_filename="Li1_1.nwout")
    handler.check()
    handler.errors = ["some unhandled error"]
    before = Path("Li1_1.nw").read_text()
    assert handler.correct() == {"errors": ["some unhandled error"], "actions": None}
    assert Path("Li1_1.nw").read_text() == before


def test_correct_writes_into_directory(tmp_path, monkeypatch) -> None:
    run = tmp_path / "run"
    shutil.copytree(f"{TEST_FILES}/nwchem", run)
    monkeypatch.chdir(tmp_path)
    handler = NwchemErrorHandler(output_filename="C1N1Cl1_1.nwout")
    handler.check(directory=str(run))
    handler.correct(directory=str(run))
    assert not (tmp_path / "C1N1Cl1_1.nw").exists()
    assert "noautoz" in NwInput.from_file(run / "C1N1Cl1_1.nw").geometry_options


def test_str() -> None:
    assert str(NwchemErrorHandler()) == "NwchemErrorHandler"
