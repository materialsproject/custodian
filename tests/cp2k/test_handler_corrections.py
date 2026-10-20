"""Tests for the check/correct logic of the CP2K error handlers.

Every test runs in a scratch directory (``cp2k_dir``) holding a copy of the reference OT input
(``cp2k.inp``) and a minimal ``cp2k.out``; corrections are asserted on the rewritten input file.
"""

from __future__ import annotations

import os
import shutil
import time

import pytest
from monty.serialization import loadfn
from pymatgen.io.cp2k.inputs import Cp2kInput

from custodian.cp2k.handlers import (
    AbortHandler,
    DivergingScfErrorHandler,
    FrozenJobErrorHandler,
    NumericalPrecisionHandler,
    UnconvergedRelaxationErrorHandler,
    UnconvergedScfErrorHandler,
    WalltimeHandler,
)
from tests.cp2k.conftest import (
    CP2K_FILES,
    GEO_OPT_CONVERGED,
    GEO_OPT_NOT_CONVERGED,
    PROGRAM_ENDED,
    SCF_CONVERGED,
    SCF_NOT_CONVERGED,
    scf_block,
)


def read_ci(path="cp2k.inp") -> Cp2kInput:
    return Cp2kInput.from_file(path)


def edit_ci(update=None, unset=None, path="cp2k.inp") -> None:
    ci = read_ci(path)
    if unset:
        ci.unset(unset)
    if update:
        ci.update(update)
    ci.write_file(path)


def val(ci, path):
    """Value of the keyword at e.g. 'FORCE_EVAL/DFT/SCF/OT/MINIMIZER', or None if absent."""
    *sections, key = path.split("/")
    kw = ci.by_path("/".join(sections)).get(key)
    return None if kw is None else kw.values[0]


def make_stale(path, age=10_000) -> None:
    old = time.time() - age
    os.utime(path, (old, old))


# --------------------------------------------------------------------------- AbortHandler


def test_abort_check_cholesky_fixture(cp2k_dir) -> None:
    handler = AbortHandler(output_file=f"{CP2K_FILES}/cp2k.out.cholesky")
    assert handler.check()
    assert handler.responses == ["cholesky"]


def test_abort_check_cholesky_scf(cp2k_dir) -> None:
    (cp2k_dir / "cp2k.out").write_text(
        " *** Cholesky decompose failed: the matrix is not positive definite or ill-conditioned ***\n"
    )
    handler = AbortHandler()
    assert handler.check()
    assert handler.responses == ["cholesky_scf"]


def test_abort_check_clean(cp2k_dir) -> None:
    (cp2k_dir / "cp2k.out").write_text(SCF_CONVERGED + PROGRAM_ENDED)
    handler = AbortHandler()
    assert not handler.check()
    assert handler.responses == []


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        ("FULL_SINGLE_INVERSE", "FULL_ALL"),
        ("FULL_ALL", "FULL_SINGLE_INVERSE"),
        (None, "FULL_SINGLE_INVERSE"),  # CP2K default is FULL_ALL
        ("FULL_KINETIC", "FULL_KINETIC"),  # unrecognized: left alone
    ],
)
def test_abort_cholesky_first_switches_preconditioner(cp2k_dir, initial, expected) -> None:
    if initial is None:
        edit_ci(unset={"FORCE_EVAL": {"DFT": {"SCF": {"OT": "PRECONDITIONER"}}}})
    else:
        edit_ci(update={"FORCE_EVAL": {"DFT": {"SCF": {"OT": {"PRECONDITIONER": initial}}}}})
    handler = AbortHandler()
    handler.responses = ["cholesky"]
    result = handler.correct()

    assert result["errors"] == ["cholesky"]
    assert len(result["actions"]) == int(initial != "FULL_KINETIC")
    assert val(read_ci(), "FORCE_EVAL/DFT/SCF/OT/PRECONDITIONER") == expected


def test_abort_cholesky_second_tightens_eps_default(cp2k_dir) -> None:
    handler = AbortHandler()
    handler.responses = ["cholesky", "cholesky"]
    result = handler.correct()
    assert len(result["actions"]) == 1
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_DEFAULT") == pytest.approx(1e-12)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") is None


def test_abort_cholesky_second_falls_through_to_pgf_orb(cp2k_dir) -> None:
    # EPS_DEFAULT is already tight, so the handler moves on to the overlap matrix precision.
    edit_ci(update={"FORCE_EVAL": {"DFT": {"QS": {"EPS_DEFAULT": 1e-12}}}})
    handler = AbortHandler()
    handler.responses = ["cholesky", "cholesky"]
    result = handler.correct()
    assert len(result["actions"]) == 1
    assert val(read_ci(), "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-10)


def test_abort_cholesky_third_divides_pgf_orb(cp2k_dir) -> None:
    edit_ci(update={"FORCE_EVAL": {"DFT": {"QS": {"EPS_PGF_ORB": 1e-12}}}})
    handler = AbortHandler()
    handler.responses = ["cholesky"] * 3
    handler.correct()
    assert val(read_ci(), "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-13)


def test_abort_cholesky_fourth_drops_wfn_restart(cp2k_dir) -> None:
    edit_ci(update={"FORCE_EVAL": {"DFT": {"WFN_RESTART_FILE_NAME": "GGA-RESTART.wfn"}}})
    handler = AbortHandler()
    handler.responses = ["cholesky"] * 4
    result = handler.correct()
    assert result["errors"] == ["cholesky"]
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/WFN_RESTART_FILE_NAME") is None
    assert val(ci, "FORCE_EVAL/DFT/XC/HF/SCREENING/SCREEN_ON_INITIAL_P") is False
    assert val(ci, "FORCE_EVAL/DFT/XC/HF/SCREENING/SCREEN_P_FORCES") is False


def test_abort_cholesky_fourth_without_wfn_restart(cp2k_dir) -> None:
    before = read_ci().get_str()
    handler = AbortHandler()
    handler.responses = ["cholesky"] * 4
    assert handler.correct()["actions"] == []
    assert read_ci().get_str() == before


@pytest.mark.parametrize(("initial", "n_actions"), [(None, 1), ("RESTORE", 1), ("INVERSE", 0)])
def test_abort_cholesky_scf(cp2k_dir, initial, n_actions) -> None:
    if initial:
        edit_ci(update={"FORCE_EVAL": {"DFT": {"SCF": {"CHOLESKY": initial}}}})
    handler = AbortHandler()
    handler.responses = ["cholesky_scf"]
    result = handler.correct()
    assert result["errors"] == ["cholesky_scf"]
    assert len(result["actions"]) == n_actions
    assert val(read_ci(), "FORCE_EVAL/DFT/SCF/CHOLESKY") == "INVERSE"


def test_abort_cholesky_scf_repeat_is_noop(cp2k_dir) -> None:
    handler = AbortHandler()
    handler.responses = ["cholesky_scf", "cholesky_scf"]
    assert handler.correct()["actions"] == []


@pytest.mark.xfail(
    strict=True,
    reason="Bug: Abort/Frozen/NumericalPrecision/UnconvergedRelaxation handlers pass "
    "os.path.join(self.input_file) (no directory) to restart(), so correct(directory=...) reads the input "
    "relative to the cwd instead of the run directory.",
)
def test_abort_correct_in_other_directory(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    shutil.copy(f"{CP2K_FILES}/cp2k.inp.orig", run_dir / "cp2k.inp")
    (run_dir / "cp2k.out").write_text(PROGRAM_ENDED)
    monkeypatch.chdir(tmp_path)

    handler = AbortHandler()
    handler.responses = ["cholesky_scf"]
    handler.correct(directory=str(run_dir))
    assert val(read_ci(run_dir / "cp2k.inp"), "FORCE_EVAL/DFT/SCF/CHOLESKY") == "INVERSE"


# --------------------------------------------------------------------------- UnconvergedScfErrorHandler


@pytest.mark.parametrize(("content", "expected"), [(SCF_NOT_CONVERGED, True), (SCF_CONVERGED, False), ("", False)])
def test_unconverged_scf_check(cp2k_dir, content, expected) -> None:
    (cp2k_dir / "cp2k.out").write_text(content + PROGRAM_ENDED)
    handler = UnconvergedScfErrorHandler()
    assert handler.check() is expected
    assert handler.is_ot
    assert handler.restart is None


def test_unconverged_scf_check_records_restart_and_diag(cp2k_dir) -> None:
    edit_ci(unset={"FORCE_EVAL": {"DFT": {"SCF": "OT"}}})
    shutil.copy("cp2k.inp", "CP2K-1.restart")
    handler = UnconvergedScfErrorHandler()
    handler.check()
    assert not handler.is_ot
    assert handler.restart.endswith("CP2K-1.restart")


def _ot(**kwargs) -> dict:
    return {"FORCE_EVAL": {"DFT": {"SCF": {"OT": kwargs}}}}


@pytest.mark.parametrize(
    ("ot", "max_scf", "expected"),
    [
        pytest.param({}, 20, {"OT/MINIMIZER": "CG"}, id="diis-to-cg"),
        pytest.param({"MINIMIZER": "CG"}, 20, {"OT/LINESEARCH": "3PNT"}, id="cg-2pnt-to-3pnt"),
        pytest.param(
            {"MINIMIZER": "CG", "LINESEARCH": "3PNT"},
            20,
            {"MAX_SCF": 50, "OUTER_SCF/MAX_SCF": 8, "OT/LINESEARCH": "3PNT"},
            id="cg-3pnt-bump-max-scf",
        ),
        pytest.param(
            {"MINIMIZER": "CG", "LINESEARCH": "3PNT"},
            50,
            {
                "MAX_SCF": 50,
                "OUTER_SCF/MAX_SCF": 20,
                "OT/LINESEARCH": "2PNT",
                "OT/ROTATION": True,
                "OT/PRECONDITIONER": "FULL_SINGLE_INVERSE",
                "OT/OCCUPATION_PRECONDITIONER": False,
                "OT/ALGORITHM": "IRAC",
            },
            id="robust-ot",
        ),
        pytest.param(
            {"MINIMIZER": "BROYDEN"},
            20,
            {"OT/ALGORITHM": "IRAC", "OT/ROTATION": True},
            id="other-minimizer-robust-ot",
        ),
        pytest.param(
            {"MINIMIZER": "CG", "ALGORITHM": "IRAC", "ROTATION": True},
            50,
            {"OT/STEPSIZE": 0.05, "OT/ALGORITHM": "IRAC"},
            id="reduce-stepsize",
        ),
    ],
)
def test_unconverged_scf_correct_ot(cp2k_dir, ot, max_scf, expected) -> None:
    edit_ci(update={"FORCE_EVAL": {"DFT": {"SCF": {"MAX_SCF": max_scf, "OT": ot}}}})
    handler = UnconvergedScfErrorHandler()
    handler.is_ot = True
    result = handler.correct()

    assert result["errors"] == ["Non-converging Job"]
    assert len(result["actions"]) == 1
    ci = read_ci()
    for key, value in expected.items():
        assert val(ci, f"FORCE_EVAL/DFT/SCF/{key}") == pytest.approx(value), key


def test_unconverged_scf_correct_ot_exhausted(cp2k_dir) -> None:
    edit_ci(update=_ot(MINIMIZER="CG", ALGORITHM="IRAC", ROTATION=True, STEPSIZE=0.05))
    edit_ci(update={"FORCE_EVAL": {"DFT": {"SCF": {"MAX_SCF": 50}}}})
    before = read_ci().get_str()
    handler = UnconvergedScfErrorHandler()
    handler.is_ot = True
    assert handler.correct()["actions"] == []
    assert read_ci().get_str() == before


def _mixing(**kwargs) -> dict:
    return {"FORCE_EVAL": {"DFT": {"SCF": {"MIXING": kwargs}}}}


SMEAR = {"FORCE_EVAL": {"DFT": {"SCF": {"SMEAR": {"ELEC_TEMP": 500}}}}}


@pytest.mark.parametrize(
    ("updates", "expected", "n_actions"),
    [
        pytest.param(
            [],
            {"MIXING/METHOD": "BROYDEN_MIXING", "MIXING/ALPHA": 0.1, "ADDED_MOS": 1000, "SMEAR/ELEC_TEMP": 300},
            2,
            id="add-mixing-and-smearing",
        ),
        pytest.param(
            [_mixing(METHOD="BROYDEN_MIXING"), SMEAR],
            {"MIXING/NBUFFER": 20, "MIXING/ALPHA": 0.05, "MIXING/BETA": 0.01, "SMEAR/ELEC_TEMP": 500},
            2,
            id="nbuffer-and-alpha",
        ),
        pytest.param([_mixing(ALPHA=0.05, NBUFFER=20), SMEAR], {"MIXING/ALPHA": 0.01}, 1, id="alpha-0.01"),
        pytest.param([_mixing(ALPHA=0.01, NBUFFER=20), SMEAR], {"MIXING/ALPHA": 0.005}, 1, id="alpha-0.005"),
        pytest.param(
            [_mixing(ALPHA=0.005, BETA=0.01, NBUFFER=20), SMEAR],
            {"MIXING/ALPHA": 0.005, "MIXING/BETA": 3},
            1,
            id="increase-beta",
        ),
        pytest.param([_mixing(ALPHA=0.005, BETA=3, NBUFFER=20), SMEAR], {"MIXING/BETA": 3}, 0, id="exhausted"),
    ],
)
def test_unconverged_scf_correct_diag(cp2k_dir, updates, expected, n_actions) -> None:
    edit_ci(unset={"FORCE_EVAL": {"DFT": {"SCF": "OT"}}})
    for update in updates:
        edit_ci(update=update)
    handler = UnconvergedScfErrorHandler()
    handler.is_ot = False
    result = handler.correct()

    assert result["errors"] == ["Non-converging Job"]
    assert len(result["actions"]) == n_actions
    ci = read_ci()
    for key, value in expected.items():
        assert val(ci, f"FORCE_EVAL/DFT/SCF/{key}") == pytest.approx(value), key


def test_unconverged_scf_correct_copies_restart_file(cp2k_dir) -> None:
    edit_ci(update={"GLOBAL": {"PROJECT_NAME": "FROM_RESTART"}})
    shutil.copy("cp2k.inp", "CP2K-1.restart")
    edit_ci(update={"GLOBAL": {"PROJECT_NAME": "CP2K"}})
    handler = UnconvergedScfErrorHandler()
    handler.is_ot = True
    result = handler.correct()
    assert "file" in result["actions"][0]
    ci = read_ci()
    # The restart file replaced the input, and the OT correction was applied on top of it.
    assert val(ci, "GLOBAL/PROJECT_NAME") == "FROM_RESTART"
    assert val(ci, "FORCE_EVAL/DFT/SCF/OT/MINIMIZER") == "CG"


# --------------------------------------------------------------------------- DivergingScfErrorHandler


@pytest.mark.parametrize(
    ("conv", "expected"),
    [
        pytest.param([0.5 * 1.5**i for i in range(12)], True, id="diverging"),
        pytest.param([10 / 2**i for i in range(12)], False, id="converging"),
        pytest.param([0.01 * 1.1**i for i in range(12)], False, id="increasing-but-small"),
        pytest.param([0.5 * 1.5**i for i in range(8)], False, id="too-few-steps"),
    ],
)
def test_diverging_scf_check(cp2k_dir, conv, expected) -> None:
    (cp2k_dir / "cp2k.out").write_text(scf_block(conv) + PROGRAM_ENDED)
    assert DivergingScfErrorHandler().check() is expected


def test_diverging_scf_correct(cp2k_dir) -> None:
    result = DivergingScfErrorHandler().correct()
    assert result["errors"] == ["Diverging SCF"]
    assert len(result["actions"]) == 2
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_DEFAULT") == pytest.approx(1e-16)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-12)


def test_diverging_scf_correct_already_tight(cp2k_dir) -> None:
    edit_ci(update={"FORCE_EVAL": {"DFT": {"QS": {"EPS_DEFAULT": 1e-16, "EPS_PGF_ORB": 1e-14}}}})
    assert DivergingScfErrorHandler().correct()["actions"] == []


# --------------------------------------------------------------------------- NumericalPrecisionHandler


@pytest.mark.parametrize(
    ("conv", "expected"),
    [([1e-2, 1e-3, 1e-4, 1e-4, 1e-4, 1e-4], True), ([1e-2, 1e-3, 1e-4, 1e-4, 1e-4, 1e-5], False)],
)
def test_numerical_precision_check(cp2k_dir, conv, expected) -> None:
    (cp2k_dir / "cp2k.out").write_text(scf_block(conv) + PROGRAM_ENDED)
    assert NumericalPrecisionHandler(max_same=3).check() is expected


def test_numerical_precision_correct_gga(cp2k_dir) -> None:
    result = NumericalPrecisionHandler().correct(directory="./")
    assert result["errors"] == ["Insufficient precision"]
    assert len(result["actions"]) == 4
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/SCF/OT/MINIMIZER") == "CG"
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_DEFAULT") == pytest.approx(1e-12)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-20)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_GVG_RSPACE") == pytest.approx(1e-10)


def test_numerical_precision_correct_finer_grid(cp2k_dir) -> None:
    edit_ci(
        update={
            "FORCE_EVAL": {
                "DFT": {
                    "QS": {"EPS_DEFAULT": 1e-12, "EPS_PGF_ORB": 1e-20, "EPS_GVG_RSPACE": 1e-10},
                    "SCF": {"OT": {"MINIMIZER": "CG"}},
                }
            }
        }
    )
    result = NumericalPrecisionHandler().correct(directory="./")
    assert len(result["actions"]) == 1
    assert val(read_ci(), "FORCE_EVAL/DFT/XC/XC_GRID/USE_FINER_GRID") is True


def test_numerical_precision_correct_custom_thresholds(cp2k_dir) -> None:
    handler = NumericalPrecisionHandler(eps_default_strict=1e-14, pgf_orb_strict=1e-18, eps_gvg_strict=1e-12)
    handler.correct(directory="./")
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_DEFAULT") == pytest.approx(1e-14)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-18)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_GVG_RSPACE") == pytest.approx(1e-12)


@pytest.fixture
def hybrid_dir(cp2k_dir):
    shutil.copy(f"{CP2K_FILES}/cp2k.inp.hybrid", "cp2k.inp")
    return cp2k_dir


def test_numerical_precision_correct_hybrid(hybrid_dir) -> None:
    # This output carries the hfx_energy_potential.F:592 warning about EPS_PGF_ORB.
    shutil.copy(f"{CP2K_FILES}/cp2k.out.conv", "cp2k.out")
    result = NumericalPrecisionHandler().correct(directory="./")
    assert len(result["actions"]) == 2
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/XC/HF/SCREENING/EPS_SCHWARZ") == pytest.approx(1e-7)
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-20)
    # Hybrid-specific fixes take priority over the generic ones.
    assert val(ci, "FORCE_EVAL/DFT/SCF/OT/MINIMIZER") == "DIIS"


def test_numerical_precision_correct_hybrid_falls_back(hybrid_dir) -> None:
    edit_ci(update={"FORCE_EVAL": {"DFT": {"XC": {"HF": {"SCREENING": {"EPS_SCHWARZ": 1e-8}}}}}})
    result = NumericalPrecisionHandler().correct(directory="./")
    # No PGF warning and screening already tight: generic fixes are applied instead.
    ci = read_ci()
    assert val(ci, "FORCE_EVAL/DFT/XC/HF/SCREENING/EPS_SCHWARZ") == pytest.approx(1e-8)
    assert val(ci, "FORCE_EVAL/DFT/SCF/OT/MINIMIZER") == "CG"
    assert val(ci, "FORCE_EVAL/DFT/QS/EPS_PGF_ORB") == pytest.approx(1e-20)
    assert len(result["actions"]) == 3


@pytest.mark.xfail(
    strict=True,
    reason="Bug: NumericalPrecisionHandler.correct defaults to directory='/.' (typo for './'), so a relative "
    "input_file is resolved against the filesystem root.",
)
def test_numerical_precision_correct_default_directory(cp2k_dir) -> None:
    NumericalPrecisionHandler().correct()
    assert val(read_ci(), "FORCE_EVAL/DFT/QS/EPS_DEFAULT") == pytest.approx(1e-12)


# --------------------------------------------------------------------------- FrozenJobErrorHandler


def test_frozen_check_finished_but_hung(cp2k_dir) -> None:
    handler = FrozenJobErrorHandler(timeout=10_000_000)
    assert not handler.check()  # just written
    make_stale("cp2k.out", age=301)
    assert handler.check()
    assert not handler.frozen_preconditioner


def test_frozen_check_running(cp2k_dir) -> None:
    (cp2k_dir / "cp2k.out").write_text(scf_block([1e-2]))
    handler = FrozenJobErrorHandler(timeout=100)
    assert not handler.check()
    make_stale("cp2k.out", age=200)
    assert handler.check()
    assert not handler.frozen_preconditioner

    result = handler.correct()
    assert result == {"errors": ["Frozen job"], "actions": []}


def test_frozen_check_preconditioner(cp2k_dir) -> None:
    shutil.copy(f"{CP2K_FILES}/cp2k.out.precondstuck", "cp2k.out")
    make_stale("cp2k.out")
    handler = FrozenJobErrorHandler(timeout=100)
    assert handler.check()
    assert handler.frozen_preconditioner


@pytest.mark.parametrize(
    ("ot", "key", "expected", "n_actions"),
    [
        ({"PRECONDITIONER": "FULL_SINGLE_INVERSE"}, "PRECONDITIONER", "FULL_ALL", 1),
        ({"PRECONDITIONER": "FULL_ALL"}, "PRECOND_SOLVER", "DIRECT", 1),
        ({"PRECONDITIONER": "FULL_ALL", "PRECOND_SOLVER": "INVERSE_CHOLESKY"}, "PRECOND_SOLVER", "INVERSE_CHOLESKY", 0),
    ],
)
def test_frozen_correct_ot_preconditioner(cp2k_dir, ot, key, expected, n_actions) -> None:
    edit_ci(update=_ot(**ot))
    handler = FrozenJobErrorHandler()
    handler.frozen_preconditioner = True
    result = handler.correct()
    assert result["errors"] == ["Frozen preconditioner"]
    assert len(result["actions"]) == n_actions
    assert not handler.frozen_preconditioner
    assert val(read_ci(), f"FORCE_EVAL/DFT/SCF/OT/{key}") == expected


@pytest.mark.parametrize(
    ("davidson", "key", "expected"),
    [
        ({"PRECONDITIONER": "FULL_SINGLE_INVERSE"}, "PRECONDITIONER", "FULL_ALL"),
        ({"PRECONDITIONER": "FULL_ALL"}, "PRECOND_SOLVER", "DIRECT"),
    ],
)
def test_frozen_correct_davidson_preconditioner(cp2k_dir, davidson, key, expected) -> None:
    edit_ci(
        unset={"FORCE_EVAL": {"DFT": {"SCF": "OT"}}},
        update={"FORCE_EVAL": {"DFT": {"SCF": {"DIAGONALIZATION": {"DAVIDSON": davidson}}}}},
    )
    handler = FrozenJobErrorHandler()
    handler.frozen_preconditioner = True
    result = handler.correct()
    assert result["errors"] == ["Frozen preconditioner"]
    assert len(result["actions"]) == 1
    assert val(read_ci(), f"FORCE_EVAL/DFT/SCF/DIAGONALIZATION/DAVIDSON/{key}") == expected


@pytest.mark.xfail(
    strict=True,
    reason="Bug: FrozenJobErrorHandler.check calls tail(self.output_file) without joining the directory, so it "
    "reads the output relative to the cwd (FileNotFoundError when cwd != directory).",
)
def test_frozen_check_in_other_directory(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "cp2k.out").write_text(scf_block([1e-2]))
    make_stale(run_dir / "cp2k.out")
    monkeypatch.chdir(tmp_path)
    assert FrozenJobErrorHandler(timeout=100).check(directory=str(run_dir))


# --------------------------------------------------------------------------- UnconvergedRelaxationErrorHandler


@pytest.mark.parametrize(("content", "expected"), [(GEO_OPT_NOT_CONVERGED, True), (GEO_OPT_CONVERGED, False)])
def test_unconverged_relaxation_check(cp2k_dir, content, expected) -> None:
    (cp2k_dir / "cp2k.out").write_text(SCF_CONVERGED + content + PROGRAM_ENDED)
    assert UnconvergedRelaxationErrorHandler().check() is expected


@pytest.fixture
def geo_opt_dir(cp2k_dir):
    edit_ci(update={"GLOBAL": {"RUN_TYPE": "GEO_OPT"}, "MOTION": {"GEO_OPT": {"MAX_ITER": 20, "OPTIMIZER": "BFGS"}}})
    return cp2k_dir


def test_unconverged_relaxation_correct_cycles_optimizers(geo_opt_dir) -> None:
    handler = UnconvergedRelaxationErrorHandler()

    result = handler.correct("./")
    assert result["errors"] == ["Unsuccessful relaxation"]
    assert len(result["actions"]) == 1
    ci = read_ci()
    assert val(ci, "MOTION/GEO_OPT/OPTIMIZER") == "CG"
    assert val(ci, "MOTION/GEO_OPT/MAX_ITER") == 40
    assert val(ci, "MOTION/GEO_OPT/CG/LINE_SEARCH/TYPE") == "2PNT"
    assert handler.optimizer_id == 2

    handler.correct("./")
    ci = read_ci()
    assert val(ci, "MOTION/GEO_OPT/OPTIMIZER") == "BFGS"
    assert val(ci, "MOTION/GEO_OPT/MAX_ITER") == 60
    assert handler.optimizer_id == 3


def test_unconverged_relaxation_correct_max_total_iter(geo_opt_dir) -> None:
    handler = UnconvergedRelaxationErrorHandler(max_iter=20, max_total_iter=30)
    assert handler.correct("./") == {"errors": ["Unsuccessful relaxation"], "actions": []}
    assert val(read_ci(), "MOTION/GEO_OPT/MAX_ITER") == 20


def test_unconverged_relaxation_correct_out_of_optimizers(geo_opt_dir) -> None:
    handler = UnconvergedRelaxationErrorHandler(optimizers=("BFGS",))
    assert handler.correct("./") == {"errors": ["Unsuccessful relaxation"], "actions": []}
    assert val(read_ci(), "MOTION/GEO_OPT/OPTIMIZER") == "BFGS"


# --------------------------------------------------------------------------- WalltimeHandler


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (" *** GLOBAL|  Run will be stopped: exceeded requested execution time ***\n" + PROGRAM_ENDED, True),
        (SCF_CONVERGED + PROGRAM_ENDED, False),
    ],
)
def test_walltime_check(cp2k_dir, content, expected) -> None:
    (cp2k_dir / "cp2k.out").write_text(content)
    assert WalltimeHandler().check() is expected


@pytest.mark.parametrize("enable_checkpointing", [True, False])
def test_walltime_correct(cp2k_dir, enable_checkpointing) -> None:
    result = WalltimeHandler(enable_checkpointing=enable_checkpointing).correct(directory=str(cp2k_dir))
    assert result == {"errors": ["Walltime error"], "actions": []}
    checkpoint = cp2k_dir / "checkpoint.json"
    assert checkpoint.exists() is enable_checkpointing
    if enable_checkpointing:
        assert loadfn(checkpoint) == {"_path": str(cp2k_dir)}
