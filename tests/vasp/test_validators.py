import logging
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from custodian.utils import tracked_lru_cache
from custodian.vasp.validators import (
    VaspAECCARValidator,
    VaspFilesValidator,
    VaspNpTMDValidator,
    VasprunXMLValidator,
    check_broken_chgcar,
)
from tests.conftest import TEST_FILES


@pytest.fixture(autouse=True)
def _clear_tracked_cache() -> None:
    """Clear the cache of the stored functions between the tests."""
    tracked_lru_cache.tracked_cache_clear()


class TestVasprunXMLValidator:
    def test_check_and_correct(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(f"{TEST_FILES}/bad_vasprun")
        handler = VasprunXMLValidator()
        assert handler.check()

        # Unconverged still has a valid vasprun.
        monkeypatch.chdir(tmp_path)
        shutil.copy(f"{TEST_FILES}/unconverged/vasprun.xml.electronic", "vasprun.xml")
        assert not handler.check()

    def test_as_dict(self) -> None:
        handler = VasprunXMLValidator()
        dct = handler.as_dict()
        h2 = VasprunXMLValidator.from_dict(dct)
        assert isinstance(h2, VasprunXMLValidator)


class TestVaspFilesValidator:
    def test_check_and_correct(self, monkeypatch) -> None:
        # just an example where CONTCAR is not present
        monkeypatch.chdir(f"{TEST_FILES}/positive_energy")
        handler = VaspFilesValidator()
        assert handler.check()

        monkeypatch.chdir(f"{TEST_FILES}/postprocess")
        assert not handler.check()

    def test_as_dict(self) -> None:
        handler = VaspFilesValidator()
        dct = handler.as_dict()
        h2 = VaspFilesValidator.from_dict(dct)
        assert isinstance(h2, VaspFilesValidator)


class TestVaspNpTMDValidator:
    def test_check_and_correct(self) -> None:
        # NPT-AIMD using correct VASP
        handler = VaspNpTMDValidator()
        assert not handler.check(directory=f"{TEST_FILES}/npt_common")

        # NVT-AIMD using correct VASP
        assert not handler.check(directory=f"{TEST_FILES}/npt_nvt")

        # NPT-AIMD using incorrect VASP
        assert handler.check(directory=f"{TEST_FILES}/npt_bad_vasp")

    def test_as_dict(self) -> None:
        handler = VaspNpTMDValidator()
        dct = handler.as_dict()
        h2 = VaspNpTMDValidator.from_dict(dct)
        assert isinstance(h2, VaspNpTMDValidator)


class TestVaspAECCARValidator:
    def test_check_and_correct(self, monkeypatch) -> None:
        # NPT-AIMD using correct VASP
        monkeypatch.chdir(f"{TEST_FILES}/bad_aeccar")
        handler = VaspAECCARValidator()
        assert handler.check()


def test_vasprun_xml_validator_logs_context(tmp_path, caplog) -> None:
    """A truncated vasprun.xml is flagged and the tails of the output files are logged."""
    (tmp_path / "vasprun.xml").write_text('<?xml version="1.0"?>\n<modeling>\n <generator>\n')
    (tmp_path / "vasp.out").write_text("".join(f"line {i}\n" for i in range(20)))
    (tmp_path / "std_err.txt").write_text("forrtl: severe (174): SIGSEGV\n")
    with caplog.at_level(logging.ERROR, logger="VasprunXMLValidator"):
        assert VasprunXMLValidator().check(directory=str(tmp_path))
    (record,) = caplog.records
    assert record.output_file_tail == "".join(f"line {i}\n" for i in range(10, 20))
    assert record.stderr_file_tail == "forrtl: severe (174): SIGSEGV\n"
    assert record.vasprun_st_size == (tmp_path / "vasprun.xml").stat().st_size
    assert record.vasprun_tail.startswith('<?xml version="1.0"?>')


def _chgcar(data: np.ndarray) -> SimpleNamespace:
    return SimpleNamespace(data={"total": data})


@pytest.mark.parametrize(
    ("data", "diff_thresh", "expected"),
    [
        (np.ones((6, 6, 6)), None, False),
        (-np.ones((6, 6, 6)), None, True),  # > 100 negative values
        (np.linspace(1, 2, 216).reshape(6, 6, 6), 0.5, False),
        (np.pad(np.full((1, 1, 1), 100.0), ((0, 5), (0, 5), (0, 5)), constant_values=1.0), 0.5, True),
    ],
)
def test_check_broken_chgcar(data, diff_thresh, expected) -> None:
    assert check_broken_chgcar(_chgcar(data), diff_thresh=diff_thresh) is expected
