import re
import shutil
from pathlib import Path

import pytest
from pymatgen.io.feff.inputs import Tags

from custodian.feff.handlers import UnconvergedErrorHandler
from tests.conftest import TEST_FILES

__author__ = "Chen Zheng"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Chen Zheng"
__email__ = "chz022@ucsd.edu"
__date__ = "Oct 18, 2017"

RESTART_ACTION = {"dict": "PARAMETERS", "action": {"_set": {"RESTART": []}}}


@pytest.fixture
def feff_dir(tmp_path, monkeypatch) -> Path:
    shutil.copytree(f"{TEST_FILES}/feff_unconverged", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def set_scf(directory: Path, scf: list, restart: bool = False) -> None:
    """Rewrite the SCF card (and optionally add RESTART) in PARAMETERS."""
    params = directory / "PARAMETERS"
    text = re.sub(r"^SCF .*$", "SCF " + " ".join(map(str, scf)), params.read_text(), flags=re.MULTILINE)
    if restart:
        text = "RESTART\n" + text
    params.write_text(text)


def test_check_unconverged(feff_dir) -> None:
    handler = UnconvergedErrorHandler()
    assert handler.check()
    dct = handler.correct()
    assert dct["errors"] == ["Non-converging job"]
    assert dct["actions"] == [
        RESTART_ACTION,
        {"action": {"_set": {"SCF": [7, 0, 100, 0.2, 3]}}, "dict": "PARAMETERS"},
    ]
    # Inputs are backed up and PARAMETERS / feff.inp are rewritten.
    assert list(feff_dir.glob("error.1.tar.gz"))
    tags = Tags.from_file(feff_dir / "PARAMETERS")
    assert tags["SCF"] == [7, 0, 100, 0.2, 3]
    assert "RESTART" in tags
    assert "SCF 7 0 100 0.2 3" in (feff_dir / "feff.inp").read_text()


@pytest.mark.parametrize(
    ("log_text", "expected"),
    [
        ("blah\nConvergence reached in 10 iterations.\n", False),
        ("blah\nConvergence not reached; ran out of iterations.\n", True),
        ("no convergence info here\n", None),
    ],
)
def test_check(tmp_path, log_text, expected) -> None:
    (tmp_path / "out.dat").write_text(log_text)
    handler = UnconvergedErrorHandler(output_filename="out.dat")
    assert handler.check(directory=str(tmp_path)) is expected


@pytest.mark.parametrize(
    ("scf_in", "scf_out"),
    [
        # nscmt < 100 and ca == 0.2: raise nscmt to 100, set nmix = 3
        ([7, 0, 30, 0.2, 1], [7, 0, 100, 0.2, 3]),
        # nscmt == 100, nmix == 3, ca > 0.01: halve ca
        ([7, 0, 100, 0.2, 3], [7, 0, 100, 0.1, 3]),
        ([7, 0, 100, 0.05, 3], [7, 0, 100, 0.03, 3]),
        # nmix == 3 and ca == 0.01: ca = 0.05, nmix = 5
        ([7, 0, 100, 0.01, 3], [7, 0, 100, 0.05, 5]),
        # nmix == 5 and ca == 0.05: nmix = 10
        ([7, 0, 100, 0.05, 5], [7, 0, 100, 0.05, 10]),
        # nmix == 10 and ca < 0.2: double ca
        ([7, 0, 100, 0.05, 10], [7, 0, 100, 0.1, 10]),
        ([7, 0, 100, 0.1, 10], [7, 0, 100, 0.2, 10]),
    ],
)
@pytest.mark.parametrize("has_restart", [False, True])
def test_correct_ladder(feff_dir, scf_in, scf_out, has_restart) -> None:
    set_scf(feff_dir, scf_in, restart=has_restart)
    dct = UnconvergedErrorHandler().correct(directory=str(feff_dir))
    scf_action = {"dict": "PARAMETERS", "action": {"_set": {"SCF": scf_out}}}
    expected = [scf_action] if has_restart else [RESTART_ACTION, scf_action]
    assert dct == {"errors": ["Non-converging job"], "actions": expected}
    tags = Tags.from_file(feff_dir / "PARAMETERS")
    assert tags["SCF"] == scf_out
    assert "RESTART" in tags


@pytest.mark.parametrize(
    "scf",
    [
        [7, 0, 100, 0.2, 10],  # end of the nmix = 10 loop
        [7, 0, 50, 0.1, 3],  # nscmt < 100 but ca != 0.2
    ],
)
def test_correct_unfixable(feff_dir, scf) -> None:
    set_scf(feff_dir, scf)
    params_before = (feff_dir / "PARAMETERS").read_text()
    dct = UnconvergedErrorHandler().correct()
    assert dct == {"errors": ["Non-converging job"], "actions": None}
    assert (feff_dir / "PARAMETERS").read_text() == params_before


def test_correct_full_ladder(feff_dir) -> None:
    """Applying correct() repeatedly walks the whole ladder and terminates."""
    handler = UnconvergedErrorHandler()
    history = []
    for _ in range(20):
        dct = handler.correct()
        if dct["actions"] is None:
            break
        history.append(Tags.from_file(feff_dir / "PARAMETERS")["SCF"][2:])
    else:
        pytest.fail("Correction ladder did not terminate")
    assert history == [
        [100, 0.2, 3],
        [100, 0.1, 3],
        [100, 0.05, 3],
        [100, 0.03, 3],
        [100, 0.01, 3],
        [100, 0.05, 5],
        [100, 0.05, 10],
        [100, 0.1, 10],
        [100, 0.2, 10],
    ]
