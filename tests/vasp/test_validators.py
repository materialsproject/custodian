import os
import shutil

import pytest

from custodian import TEST_FILES
from custodian.vasp.validators import VaspAECCARValidator, VaspFilesValidator, VaspNpTMDValidator, VasprunXMLValidator


@pytest.fixture(autouse=True)
def _clear_tracked_cache():
    """
    Clear the cache of the stored functions between the tests.
    """
    from custodian.utils import tracked_lru_cache

    tracked_lru_cache.tracked_cache_clear()


class TestVasprunXMLValidator:
    def test_check_and_correct(self):
        os.chdir(f"{TEST_FILES}/bad_vasprun")
        handler = VasprunXMLValidator()
        assert handler.check()

        # Unconverged still has a valid vasprun.
        os.chdir(f"{TEST_FILES}/unconverged")
        shutil.copy("vasprun.xml.electronic", "vasprun.xml")
        assert not handler.check()
        os.remove("vasprun.xml")

    def test_as_dict(self):
        handler = VasprunXMLValidator()
        dct = handler.as_dict()
        h2 = VasprunXMLValidator.from_dict(dct)
        assert isinstance(h2, VasprunXMLValidator)


class TestVaspFilesValidator:
    def test_check_and_correct(self):
        # just an example where CONTCAR is not present
        os.chdir(f"{TEST_FILES}/positive_energy")
        handler = VaspFilesValidator()
        assert handler.check()

        os.chdir(f"{TEST_FILES}/postprocess")
        assert not handler.check()

    def test_as_dict(self):
        handler = VaspFilesValidator()
        dct = handler.as_dict()
        h2 = VaspFilesValidator.from_dict(dct)
        assert isinstance(h2, VaspFilesValidator)


class TestVaspNpTMDValidator:
    def test_check_and_correct(self):
        # NPT-AIMD using correct VASP
        os.chdir(f"{TEST_FILES}/npt_common")
        handler = VaspNpTMDValidator()
        assert not handler.check()

        # NVT-AIMD using correct VASP
        os.chdir(f"{TEST_FILES}/npt_nvt")
        assert not handler.check()

        # NPT-AIMD using incorrect VASP
        os.chdir(f"{TEST_FILES}/npt_bad_vasp")
        assert handler.check()

    def test_as_dict(self):
        handler = VaspNpTMDValidator()
        dct = handler.as_dict()
        h2 = VaspNpTMDValidator.from_dict(dct)
        assert isinstance(h2, VaspNpTMDValidator)


class TestVaspAECCARValidator:
    def test_check_and_correct(self):
        # NPT-AIMD using correct VASP
        os.chdir(f"{TEST_FILES}/bad_aeccar")
        handler = VaspAECCARValidator()
        assert handler.check()
