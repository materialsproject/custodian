"""Shared fixtures and helpers for the CP2K tests."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from tests.conftest import TEST_FILES

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

CP2K_FILES = f"{TEST_FILES}/cp2k"

PROGRAM_ENDED = "  **** **** ******  **  PROGRAM ENDED AT                 2020-08-28 13:22:02.283\n"
SCF_CONVERGED = " *** SCF run converged in    10 steps ***\n"
SCF_NOT_CONVERGED = " *** WARNING in qs_scf.F:542 :: SCF run NOT converged ***\n"
GEO_OPT_CONVERGED = " ***                    GEOMETRY OPTIMIZATION COMPLETED                      ***\n"
GEO_OPT_NOT_CONVERGED = " ***                 MAXIMUM NUMBER OF OPTIMIZATION STEPS REACHED            ***\n"


def scf_block(conv: Sequence[float]) -> str:
    """Build a minimal CP2K SCF table with the given convergence values."""
    # The pymatgen table parser does not match a header on the very first line of the file.
    lines = [
        " SCF WAVEFUNCTION OPTIMIZATION",
        "",
        "  Step     Update method      Time    Convergence         Total energy    Change",
        "  ------------------------------------------------------------------------------",
    ]
    lines += [
        f"     {i} OT DIIS     0.15E+00    0.5     {val:.8f}      -237.4419935429 -2.37E+02"
        for i, val in enumerate(conv, start=1)
    ]
    return "\n".join(lines) + "\n\n"


@pytest.fixture
def cp2k_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch run directory (also the cwd) holding a copy of the reference OT input as cp2k.inp."""
    shutil.copy(f"{CP2K_FILES}/cp2k.inp.orig", tmp_path / "cp2k.inp")
    (tmp_path / "cp2k.out").write_text(PROGRAM_ENDED)
    monkeypatch.chdir(tmp_path)
    return tmp_path
