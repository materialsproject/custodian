import os
import shutil

from custodian.vasp.validators import VaspAECCARValidator, VaspFilesValidator, VaspNpTMDValidator, VasprunXMLValidator

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_files")


class TestVasprunXMLValidator:
    def test_check_and_correct(self):
        os.chdir(os.path.join(test_dir, "bad_vasprun"))
        h = VasprunXMLValidator()
        assert h.check()

        # Unconverged still has a valid vasprun.
        os.chdir(os.path.join(test_dir, "unconverged"))
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
        os.chdir(os.path.join(test_dir, "positive_energy"))
        h = VaspFilesValidator()
        assert h.check()

        os.chdir(os.path.join(test_dir, "postprocess"))
        assert not h.check()

    def test_as_dict(self):
        h = VaspFilesValidator()
        d = h.as_dict()
        h2 = VaspFilesValidator.from_dict(d)
        assert isinstance(h2, VaspFilesValidator)


class TestVaspNpTMDValidator:
    def test_check_and_correct(self):
        # NPT-AIMD using correct VASP
        os.chdir(os.path.join(test_dir, "npt_common"))
        h = VaspNpTMDValidator()
        assert not h.check()

        # NVT-AIMD using correct VASP
        os.chdir(os.path.join(test_dir, "npt_nvt"))
        assert not h.check()

        # NPT-AIMD using incorrect VASP
        os.chdir(os.path.join(test_dir, "npt_bad_vasp"))
        assert h.check()

    def test_as_dict(self):
        h = VaspNpTMDValidator()
        d = h.as_dict()
        h2 = VaspNpTMDValidator.from_dict(d)
        assert isinstance(h2, VaspNpTMDValidator)


class TestVaspAECCARValidator:
    def test_check_and_correct(self):
        # NPT-AIMD using correct VASP
        os.chdir(os.path.join(test_dir, "bad_aeccar"))
        h = VaspAECCARValidator()
        assert h.check()
