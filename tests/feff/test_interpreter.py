import shutil

import pytest
from pymatgen.io.feff.inputs import Tags

from custodian.feff.interpreter import FeffModder
from tests.conftest import TEST_FILES


@pytest.fixture
def feff_dir(tmp_path, monkeypatch):
    shutil.copytree(f"{TEST_FILES}/feff_unconverged", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_apply_dict_action(feff_dir) -> None:
    FeffModder(directory=str(feff_dir)).apply_actions(
        [{"dict": "PARAMETERS", "action": {"_set": {"SCF": [7, 0, 100, 0.1, 3]}}}]
    )
    assert Tags.from_file(feff_dir / "PARAMETERS")["SCF"] == [7, 0, 100, 0.1, 3]
    assert "SCF 7 0 100 0.1 3" in (feff_dir / "feff.inp").read_text()


def test_apply_file_action(feff_dir) -> None:
    params_before = (feff_dir / "PARAMETERS").read_text()
    inp_before = (feff_dir / "feff.inp").read_text()
    FeffModder(directory=str(feff_dir)).apply_actions(
        [{"file": "log1.dat", "action": {"_file_copy": {"dest": "log1.dat.bak"}}}]
    )
    assert (feff_dir / "log1.dat.bak").read_text() == (feff_dir / "log1.dat").read_text()
    # File-only actions must not rewrite the FEFF input files.
    assert (feff_dir / "PARAMETERS").read_text() == params_before
    assert (feff_dir / "feff.inp").read_text() == inp_before


def test_apply_bad_action(feff_dir) -> None:
    with pytest.raises(ValueError, match="Unrecognized format"):
        FeffModder(directory=str(feff_dir)).apply_actions([{"bad": "PARAMETERS", "action": {}}])
