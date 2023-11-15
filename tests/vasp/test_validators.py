import os
import shutil

from custodian import TEST_FILES
from custodian.vasp.validators import VaspAECCARValidator, VaspFilesValidator, VaspNpTMDValidator, VasprunXMLValidator


class TestVasprunXMLValidator:
    def test_check_and_correct(self):
        os.chdir(os.path.join(TEST_FILES, "bad_vasprun"))
        h = VasprunXMLValidator()
        assert h.check()

        # Unconverged still has a valid vasprun.
        os.chdir(os.path.join(TEST_FILES, "unconverged"))
        shutil.copy("vasprun.xml.electronic", "vasprun.xml")
        assert not h.check()
        os.remove("vasprun.xml")

    def test_as_dict(self):
        h = VasprunXMLValidator()
        d = h.as_dict()
        h2 = VasprunXMLValidator.from_dict(d)
        assert isinstance(h2, VasprunXMLValidator)


class TestVaspFilesValidator:
    def test_check_and_correct(self):
        # just an example where CONTCAR is not present
        os.chdir(os.path.join(TEST_FILES, "positive_energy"))
        h = VaspFilesValidator()
        assert h.check()

        os.chdir(os.path.join(TEST_FILES, "postprocess"))
        assert not h.check()

    def test_as_dict(self):
        h = VaspFilesValidator()
        d = h.as_dict()
        h2 = VaspFilesValidator.from_dict(d)
        assert isinstance(h2, VaspFilesValidator)


class TestVaspNpTMDValidator:
    def test_check_and_correct(self):
        # NPT-AIMD using correct VASP
        os.chdir(os.path.join(TEST_FILES, "npt_common"))
        h = VaspNpTMDValidator()
        assert not h.check()

        # NVT-AIMD using correct VASP
        os.chdir(os.path.join(TEST_FILES, "npt_nvt"))
        assert not h.check()

        # NPT-AIMD using incorrect VASP
        os.chdir(os.path.join(TEST_FILES, "npt_bad_vasp"))
        assert h.check()

    def test_as_dict(self):
        h = VaspNpTMDValidator()
        d = h.as_dict()
        h2 = VaspNpTMDValidator.from_dict(d)
        assert isinstance(h2, VaspNpTMDValidator)


class TestVaspAECCARValidator:
    def test_check_and_correct(self):
        # NPT-AIMD using correct VASP
        os.chdir(os.path.join(TEST_FILES, "bad_aeccar"))
        h = VaspAECCARValidator()
        assert h.check()
