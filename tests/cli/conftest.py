"""Shared fixtures for the custodian.cli tests."""

from __future__ import annotations

import importlib
import logging
import shutil
from typing import TYPE_CHECKING

import pytest

from tests.conftest import TEST_FILES

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

VASP_INPUTS = ("INCAR", "KPOINTS", "POSCAR", "POTCAR")


@pytest.fixture(autouse=True)
def _no_log_file(monkeypatch) -> None:
    """The CLI modules call logging.basicConfig(filename="run.log"); keep that out of cwd and the root logger."""
    monkeypatch.setattr(logging, "basicConfig", lambda **_kwargs: None)


@pytest.fixture
def vasp_dir(tmp_path: Path, monkeypatch) -> Path:
    """A scratch dir containing the standard VASP inputs from tests/files, set as cwd."""
    for fname in VASP_INPUTS:
        shutil.copy(f"{TEST_FILES}/{fname}", tmp_path / fname)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def import_cli(name: str) -> ModuleType:
    """Import a cli module lazily so its import-time logging.basicConfig is neutralized by _no_log_file."""
    return importlib.import_module(f"custodian.cli.{name}")
