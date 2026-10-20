"""Tests for the CP2K output validator."""

from __future__ import annotations

import pytest

from custodian.cp2k.validators import Cp2kOutputValidator
from tests.cp2k.conftest import (
    CP2K_FILES,
    GEO_OPT_CONVERGED,
    GEO_OPT_NOT_CONVERGED,
    PROGRAM_ENDED,
    SCF_CONVERGED,
    SCF_NOT_CONVERGED,
)


@pytest.mark.parametrize(
    ("content", "failed"),
    [
        pytest.param(SCF_CONVERGED + PROGRAM_ENDED, False, id="completed-static"),
        pytest.param(
            PROGRAM_ENDED,
            False,
            id="completed-no-scf-info",
            marks=pytest.mark.xfail(
                strict=True,
                reason="Bug: Cp2kOutput.convergence() always sets data['scf_converged'] (to [] when no SCF lines),"
                " so the [True] default in Cp2kOutputValidator.check never applies and [][-1] raises IndexError,"
                " which is swallowed and reported as a failed validation (e.g. completed FIST/MM runs).",
            ),
        ),
        pytest.param(SCF_CONVERGED + GEO_OPT_CONVERGED + PROGRAM_ENDED, False, id="completed-geo-opt"),
        pytest.param(SCF_CONVERGED, True, id="not-ended"),
        pytest.param(SCF_NOT_CONVERGED + PROGRAM_ENDED, True, id="scf-not-converged"),
        pytest.param(SCF_CONVERGED + GEO_OPT_NOT_CONVERGED + PROGRAM_ENDED, True, id="geo-opt-not-converged"),
        pytest.param("\x00\x01 garbled \xff\n", True, id="garbled"),
        pytest.param("", True, id="empty"),
    ],
)
def test_check(tmp_path, content, failed) -> None:
    (tmp_path / "cp2k.out").write_text(content)
    validator = Cp2kOutputValidator()
    assert validator.check(directory=str(tmp_path)) is failed
    assert validator._check is failed


def test_check_custom_output_file(tmp_path) -> None:
    (tmp_path / "run.log").write_text(SCF_CONVERGED + PROGRAM_ENDED)
    assert Cp2kOutputValidator(output_file="run.log").check(directory=str(tmp_path)) is False
    # Default name is absent in this directory.
    assert Cp2kOutputValidator().check(directory=str(tmp_path)) is True


def test_check_missing_file(tmp_path) -> None:
    validator = Cp2kOutputValidator()
    assert validator.check(directory=str(tmp_path)) is True
    assert validator._check is True


@pytest.mark.parametrize(
    ("fname", "failed"),
    [("cp2k.out.unconverged", True), ("cp2k.out.precondstuck", True), ("cp2k.out.cholesky", True)],
)
def test_check_fixture_outputs(fname, failed) -> None:
    validator = Cp2kOutputValidator(output_file=fname)
    assert validator.check(directory=CP2K_FILES) is failed


def test_properties() -> None:
    validator = Cp2kOutputValidator()
    assert validator.output_file == "cp2k.out"
    assert validator._check is False
    assert validator.kill is True
    assert validator.exit is True
    assert validator.no_children is True
