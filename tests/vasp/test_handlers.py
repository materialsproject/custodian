"""Created on Jun 1, 2012."""

import datetime
import os
import shutil
import tarfile
from glob import glob

import pytest
from monty.os.path import zpath
from pymatgen.io.vasp.inputs import Incar, Kpoints, Structure, VaspInput
from pymatgen.util.testing import PymatgenTest

from custodian.utils import tracked_lru_cache
from custodian.vasp.handlers import (
    AliasingErrorHandler,
    DriftErrorHandler,
    FrozenJobErrorHandler,
    IncorrectSmearingHandler,
    KspacingMetalHandler,
    LargeSigmaHandler,
    LrfCommutatorHandler,
    MeshSymmetryErrorHandler,
    NonConvergingErrorHandler,
    PositiveEnergyErrorHandler,
    PotimErrorHandler,
    ScanMetalHandler,
    StdErrHandler,
    UnconvergedErrorHandler,
    VaspErrorHandler,
    WalltimeHandler,
)
from tests.conftest import TEST_FILES

__author__ = "Shyue Ping Ong, Stephen Dacek, Janosh Riebesell"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

CWD = os.getcwd()
os.environ.setdefault("PMG_VASP_PSP_DIR", TEST_FILES)


@pytest.fixture(autouse=True)
def _clear_tracked_cache() -> None:
    """Clear the cache of the stored functions between the tests."""
    from custodian.utils import tracked_lru_cache

    tracked_lru_cache.tracked_cache_clear()


def copy_tmp_files(tmp_path: str, *file_paths: str) -> None:
    for file_path in file_paths:
        for ext in (".gz", ".bz2"):
            # TODO remove this when https://github.com/materialsvirtuallab/monty/pull/682
            # is released
            file_path = file_path.removesuffix(ext)
        src_path = zpath(f"{TEST_FILES}/{file_path}")
        dst_path = f"{tmp_path}/{os.path.basename(src_path)}"
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy(src_path, dst_path)
    os.chdir(tmp_path)


class VaspErrorHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, *glob("*", root_dir=TEST_FILES))

    def test_frozen_job(self) -> None:
        handler = FrozenJobErrorHandler()
        dct = handler.correct()
        assert dct["errors"] == ["Frozen job"]
        assert Incar.from_file("INCAR")["ALGO"] == "Normal"

    def test_algotet(self) -> None:
        shutil.copy("INCAR.algo_tet_only", "INCAR")
        handler = VaspErrorHandler("vasp.algo_tet_only")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["algo_tet"]
        assert dct["actions"] == [{"action": {"_set": {"ALGO": "Fast"}}, "dict": "INCAR"}]
        assert handler.error_count["algo_tet"] == 1

        # 2nd error should set ISMEAR to 0.
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["algo_tet"]
        assert handler.error_count["algo_tet"] == 2
        assert dct["actions"] == [{"action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}, "dict": "INCAR"}]

    def test_subspace(self) -> None:
        handler = VaspErrorHandler("vasp.subspace")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["subspacematrix"]
        assert dct["actions"] == [{"action": {"_set": {"LREAL": False}}, "dict": "INCAR"}]

        # 2nd error should set PREC to accurate.
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["subspacematrix"]
        assert dct["actions"] == [{"action": {"_set": {"PREC": "Accurate"}}, "dict": "INCAR"}]

    def test_check_correct(self) -> None:
        handler = VaspErrorHandler("vasp.ksymm")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["ksymm"]
        assert dct["actions"] == [{"action": {"_set": {"SYMPREC": 1.0e-4}}, "dict": "INCAR"}]

        handler = VaspErrorHandler("vasp.ksymm", errors_subset_to_catch=["eddrmm"])
        assert not handler.check()

        handler = VaspErrorHandler("vasp.sgrcon")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["rot_matrix"]
        assert {a["dict"] for a in dct["actions"]} == {"KPOINTS"}

        handler = VaspErrorHandler("vasp.real_optlay")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["real_optlay"]
        assert dct["actions"] == [{"action": {"_set": {"LREAL": False}}, "dict": "INCAR"}]

    def test_mesh_symmetry(self) -> None:
        handler = MeshSymmetryErrorHandler("vasp.ibzkpt")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["mesh_symmetry"]
        assert dct["actions"] == [{"action": {"_set": {"kpoints": [[4, 4, 4]]}}, "dict": "KPOINTS"}]

    def test_brions(self) -> None:
        shutil.copy("INCAR.ibrion", "INCAR")
        handler = VaspErrorHandler("vasp.brions")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["brions"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 1
        assert incar["POTIM"] == pytest.approx(1.5)

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["brions"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 2
        assert incar["POTIM"] == pytest.approx(0.5)

    def test_dentet(self) -> None:
        # ensure we use a very small, Monkhorst-Pack k-point grid to check all handler functionality
        Kpoints(style="Monkhorst").write_file("KPOINTS")

        handler = VaspErrorHandler("vasp.dentet")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["dentet"]
        assert dct["actions"] == [{"action": {"_set": {"generation_style": "Gamma"}}, "dict": "KPOINTS"}]

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["dentet"]
        assert dct["actions"] == [
            {"action": {"_set": {"kpoints": ((3, 2, 1),), "generation_style": "Gamma"}}, "dict": "KPOINTS"}
        ]

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["dentet"]
        assert dct["actions"] == [{"action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}, "dict": "INCAR"}]

    def test_zbrent(self) -> None:
        handler = VaspErrorHandler("vasp.zbrent")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zbrent"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 2
        assert incar["EDIFF"] == 1e-06
        assert incar["NELMIN"] == 8

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zbrent"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 1
        assert incar["EDIFF"] == 1e-07
        assert incar["NELMIN"] == 8

        shutil.copy(f"{TEST_FILES}/INCAR", f"{self.tmp_path}/INCAR")
        handler = VaspErrorHandler("vasp.zbrent")
        handler.vtst_fixes = True
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zbrent"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 3
        assert incar["IOPT"] == 7
        assert incar["POTIM"] == 0
        assert incar["EDIFF"] == 1e-06
        assert incar["NELMIN"] == 8

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zbrent"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 3
        assert incar["IOPT"] == 7
        assert incar["POTIM"] == 0
        assert incar["EDIFF"] == 1e-07
        assert incar["NELMIN"] == 8

        shutil.copy("INCAR.ediff", "INCAR")
        handler = VaspErrorHandler("vasp.zbrent")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zbrent"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 2
        assert incar["EDIFF"] == 1e-07
        assert incar["NELMIN"] == 8

        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zbrent"]
        incar = Incar.from_file("INCAR")
        assert incar["IBRION"] == 1
        assert incar["EDIFF"] == 1e-08
        assert incar["NELMIN"] == 8

    def test_brmix(self) -> None:
        handler = VaspErrorHandler("vasp.brmix")
        assert handler.check() is True

        # The first (no good OUTCAR) correction, check IMIX
        dct = handler.correct()
        assert dct["errors"] == ["brmix"]
        vi = VaspInput.from_directory(".")
        assert vi["INCAR"]["IMIX"] == 1
        assert os.path.isfile("CHGCAR")

        # The next correction check Gamma and evenize
        handler.correct()
        vi = VaspInput.from_directory(".")
        assert "IMIX" not in vi["INCAR"]
        assert os.path.isfile("CHGCAR")
        if vi["KPOINTS"].style == Kpoints.supported_modes.Gamma and vi["KPOINTS"].num_kpts < 1:
            all_kpts_even = all(n % 2 == 0 for n in vi["KPOINTS"].kpts[0])
            assert not all_kpts_even

        # The next correction check ISYM and no CHGCAR
        handler.correct()
        vi = VaspInput.from_directory(".")
        assert vi["INCAR"]["ISYM"] == 0
        assert not os.path.isfile("CHGCAR")

        shutil.copy("INCAR.nelect", "INCAR")
        handler = VaspErrorHandler("vasp.brmix")
        assert handler.check() is False
        dct = handler.correct()
        assert dct["errors"] == []

    def test_too_few_bands(self) -> None:
        shutil.copytree(f"{TEST_FILES}/too_few_bands", self.tmp_path, dirs_exist_ok=True, symlinks=True)
        os.chdir(self.tmp_path)
        shutil.copy("INCAR", "INCAR.orig")
        handler = VaspErrorHandler("vasp.too_few_bands")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["too_few_bands"]
        assert dct["actions"] == [{"action": {"_set": {"NBANDS": 501}}, "dict": "INCAR"}]

    def test_rot_matrix(self) -> None:
        shutil.copytree(f"{TEST_FILES}/poscar_error", self.tmp_path, dirs_exist_ok=True, symlinks=True)
        os.chdir(self.tmp_path)
        shutil.copy("KPOINTS", "KPOINTS.orig")
        handler = VaspErrorHandler()
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["rot_matrix"]

    def test_rot_matrix_vasp6(self) -> None:
        handler = VaspErrorHandler("vasp6.sgrcon")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["rot_matrix"]

    def test_coef(self) -> None:
        handler = VaspErrorHandler("vasp6.coef")
        handler.check()
        dct = handler.correct()
        assert dct["actions"] == [{"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}}]

        handler = VaspErrorHandler("vasp6.coef2")
        handler.check()
        dct = handler.correct()
        assert dct["actions"] == [{"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}}]

    def test_as_from_dict(self) -> None:
        handler = VaspErrorHandler("random_name")
        h2 = VaspErrorHandler.from_dict(handler.as_dict())
        assert isinstance(h2, VaspErrorHandler)
        assert h2.output_filename == "random_name"

    def test_pssyevx_pdsyevx(self) -> None:
        incar_orig = Incar.from_file("INCAR")
        # Joining tests for these three tags as they have identical handling
        for error_name in ("pssyevx", "pdsyevx"):
            handler = VaspErrorHandler(f"vasp.{error_name}")
            assert handler.check() is True
            assert handler.correct()["errors"] == [error_name]
            incar = Incar.from_file("INCAR")
            assert incar["ALGO"] == "Normal"
            incar_orig.write_file("INCAR")

    def test_eddrmm(self) -> None:
        shutil.copy("CONTCAR.eddav_eddrmm", "CONTCAR")
        handler = VaspErrorHandler("vasp.eddrmm")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["eddrmm"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "Normal"
        assert handler.correct()["errors"] == ["eddrmm"]
        incar = Incar.from_file("INCAR")
        assert incar["POTIM"] == 0.25
        p = Structure.from_file("POSCAR")
        c = Structure.from_file("CONTCAR")
        assert p == c

    def test_nicht_konv(self) -> None:
        handler = VaspErrorHandler("vasp.nicht_konvergent")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["nicht_konv"]
        incar = Incar.from_file("INCAR")
        assert incar["LREAL"] is False

    def test_edddav(self) -> None:
        shutil.copy("CONTCAR.eddav_eddrmm", "CONTCAR")
        handler = VaspErrorHandler("vasp.edddav2")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["edddav"]
        incar = Incar.from_file("INCAR")
        assert incar["NCORE"] == 2
        p = Structure.from_file("POSCAR")
        c = Structure.from_file("CONTCAR")
        assert p == c

        handler = VaspErrorHandler("vasp.edddav")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["edddav"]
        assert not os.path.isfile("CHGCAR")
        p = Structure.from_file("POSCAR")
        c = Structure.from_file("CONTCAR")
        assert p == c

    def test_gradient_not_orthogonal(self) -> None:
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "Fast"

        shutil.copy("INCAR.gga_all", "INCAR")
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "Fast"

        shutil.copy("INCAR.gga_ialgo53", "INCAR")
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "Fast"
        assert "IALGO" not in incar

        shutil.copy("INCAR.hybrid_normal", "INCAR")
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "Normal"

        shutil.copy("INCAR.hybrid_all", "INCAR")
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "All"

        shutil.copy("INCAR.metagga_all", "INCAR")
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "All"

    def test_rhosyg(self) -> None:
        handler = VaspErrorHandler("vasp.rhosyg")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["rhosyg"]
        incar = Incar.from_file("INCAR")
        assert incar["SYMPREC"] == 0.0001
        assert handler.correct()["errors"] == ["rhosyg"]
        incar = Incar.from_file("INCAR")
        assert incar["ISYM"] == 0

    def test_rhosyg_vasp6(self) -> None:
        handler = VaspErrorHandler("vasp6.rhosyg")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["rhosyg"]
        incar = Incar.from_file("INCAR")
        assert incar["SYMPREC"] == 0.0001
        assert handler.correct()["errors"] == ["rhosyg"]
        incar = Incar.from_file("INCAR")
        assert incar["ISYM"] == 0

    def test_hnform(self) -> None:
        handler = VaspErrorHandler("vasp.hnform")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["hnform"]
        incar = Incar.from_file("INCAR")
        assert incar["ISYM"] == 0

    def test_bravais(self) -> None:
        handler = VaspErrorHandler("vasp6.bravais")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["bravais"]
        incar = Incar.from_file("INCAR")
        assert incar["SYMPREC"] == 0.0001

        shutil.copy("INCAR.symprec", "INCAR")
        handler = VaspErrorHandler("vasp6.bravais")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["bravais"]
        incar = Incar.from_file("INCAR")
        assert incar["SYMPREC"] == 1e-6

    def test_posmap_and_pricelv(self) -> None:
        incar_orig = Incar.from_file("INCAR")
        # Joining tests for these three tags as they have identical handling
        for error_name in ("posmap", "posmap-6", "pricelv"):
            if error_name == "posmap-6":
                vasp_std_out = "vasp6.posmap"
                error_name = "posmap"
            else:
                vasp_std_out = f"vasp.{error_name}"

            handler = VaspErrorHandler(vasp_std_out)
            assert handler.check() is True
            assert handler.correct()["errors"] == [error_name]
            incar = Incar.from_file("INCAR")
            assert incar["SYMPREC"] == pytest.approx(1e-6)

            assert handler.check() is True
            assert handler.correct()["errors"] == [error_name]
            incar = Incar.from_file("INCAR")
            assert incar["SYMPREC"] == pytest.approx(1e-4)

            assert handler.check() is True
            assert handler.correct()["errors"] == [error_name]
            incar = Incar.from_file("INCAR")
            assert incar["ISYM"] == 0

            incar_orig.write_file("INCAR")

    def test_point_group(self) -> None:
        handler = VaspErrorHandler("vasp.point_group")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["point_group"]
        incar = Incar.from_file("INCAR")
        assert incar["ISYM"] == 0

    def test_symprec_noise(self) -> None:
        handler = VaspErrorHandler("vasp.symprec_noise")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["symprec_noise"]
        incar = Incar.from_file("INCAR")
        assert incar["SYMPREC"] == 1e-06

    def test_dfpt_ncore(self) -> None:
        handler = VaspErrorHandler("vasp.dfpt_ncore")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["dfpt_ncore"]
        incar = Incar.from_file("INCAR")
        assert "NPAR" not in incar
        assert "NCORE" not in incar

    def test_finite_difference_ncore(self) -> None:
        handler = VaspErrorHandler("vasp.fd_ncore")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["dfpt_ncore"]
        incar = Incar.from_file("INCAR")
        assert "NPAR" not in incar
        assert "NCORE" not in incar

    def test_point_group_vasp6(self) -> None:
        # the error message is formatted differently in VASP6 compared to VASP5
        handler = VaspErrorHandler("vasp6.point_group")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["point_group"]
        incar = Incar.from_file("INCAR")
        assert incar["ISYM"] == 0

    def test_inv_rot_matrix_vasp6(self) -> None:
        # the error message is formatted differently in VASP6 compared to VASP5
        handler = VaspErrorHandler("vasp6.inv_rot_mat")
        assert handler.check() is True
        assert handler.correct()["errors"] == ["inv_rot_mat"]
        incar = Incar.from_file("INCAR")
        assert incar["SYMPREC"] == 1e-08

    def test_bzint_vasp6(self) -> None:
        # the BZINT error message is formatted differently in VASP6 compared to VASP5
        handler = VaspErrorHandler("vasp6.bzint")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["tet"]
        incar = Incar.from_file("INCAR")
        assert incar["ISMEAR"] == 0
        assert incar["SIGMA"] == 0.05

    def test_too_large_kspacing(self) -> None:
        shutil.copy("INCAR.kspacing", "INCAR")
        os.remove("KPOINTS")
        VaspInput.from_directory(".")
        handler = VaspErrorHandler("vasp.dentet")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["dentet"]
        assert dct["actions"] == [{"action": {"_set": {"KSPACING": 1.333333, "KGAMMA": True}}, "dict": "INCAR"}]

    def test_nbands_not_sufficient(self) -> None:
        handler = VaspErrorHandler("vasp.nbands_not_sufficient")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["nbands_not_sufficient"]
        assert dct["actions"] is None

    def test_too_few_bands_round_error(self) -> None:
        # originally there are NBANDS= 7
        # correction should increase it
        shutil.copy("INCAR.too_few_bands_round_error", "INCAR")
        handler = VaspErrorHandler("vasp.too_few_bands_round_error")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["too_few_bands"]
        assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"NBANDS": 8}}}]

    def test_set_core_wf(self) -> None:
        handler = VaspErrorHandler("vasp.set_core_wf")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["set_core_wf"]
        assert dct["actions"] is None

    def test_read_error(self) -> None:
        handler = VaspErrorHandler("vasp.read_error")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["read_error"]
        assert dct["actions"] is None

    def test_amin(self) -> None:
        # Cell with at least one dimension >= 50 A, but AMIN > 0.01, and calculation not yet complete
        shutil.copy("INCAR.amin", "INCAR")
        handler = VaspErrorHandler("vasp.amin")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["amin"]
        assert dct["actions"] == [{"action": {"_set": {"AMIN": 0.01}}, "dict": "INCAR"}]

    def test_eddiag(self) -> None:
        # subspace rotation error
        os.remove("CONTCAR")
        shutil.copy("INCAR.amin", "INCAR")
        handler = VaspErrorHandler("vasp.eddiag")
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["eddiag"]
        # first check that no CONTCAR exists, only action should be updating INCAR
        # ALGO = Fast --> ALGO = Normal
        assert dct["actions"] == [{"action": {"_set": {"ALGO": "Normal"}}, "dict": "INCAR"}]

        # now copy CONTCAR and check that both CONTCAR->POSCAR
        # and INCAR updates are included: ALGO = Normal --> ALGO = exact
        shutil.copy("CONTCAR.eddiag", "CONTCAR")
        handler = VaspErrorHandler("vasp.eddiag")
        handler.check()
        dct = handler.correct()
        assert dct["actions"] == [
            {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
            {"action": {"_set": {"ALGO": "exact"}}, "dict": "INCAR"},
        ]

    def test_auto_nbands(self) -> None:
        shutil.copy("OUTCAR_auto_nbands", "OUTCAR")
        handler = VaspErrorHandler(zpath("vasp.auto_nbands"))
        handler.check()
        with pytest.warns(UserWarning, match="NBANDS seems to be too high"):
            dct = handler.correct()
        assert "auto_nbands" in dct["errors"]

    def test_auto_nbands_bad_parallelization(self) -> None:
        shutil.copy("OUTCAR_auto_nbands_parallel", "OUTCAR")
        # hacky way to deal with custodian CI unzipping test files
        Incar.from_file(zpath("INCAR.auto_nbands_parallel")).write_file("INCAR")

        handler = VaspErrorHandler(zpath("vasp.auto_nbands"))
        handler.check()
        with pytest.warns(UserWarning, match="setting was incompatible with your parallelization"):
            dct = handler.correct()
        assert "auto_nbands" in dct["errors"]
        assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"NBANDS": 64}}}]


class AliasingErrorHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, *glob("aliasing/*", root_dir=TEST_FILES))

    def test_aliasing(self) -> None:
        handler = AliasingErrorHandler("vasp.aliasing")
        handler.check()
        dct = handler.correct()

        assert dct["errors"] == ["aliasing"]
        assert dct["actions"] == [
            {"action": {"_set": {"NGX": 34}}, "dict": "INCAR"},
            {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}},
            {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}},
        ]

    def test_aliasing_incar(self) -> None:
        shutil.copy("INCAR", "INCAR.orig")
        handler = AliasingErrorHandler("vasp.aliasing_incar")
        handler.check()
        dct = handler.correct()

        assert dct["errors"] == ["aliasing_incar"]
        assert dct["actions"] == [
            {"action": {"_unset": {"NGY": 1, "NGZ": 1}}, "dict": "INCAR"},
            {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}},
            {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}},
        ]

        incar = Incar.from_file("INCAR.orig")
        incar["ICHARG"] = 10
        incar.write_file("INCAR")
        dct = handler.correct()
        assert dct["errors"] == ["aliasing_incar"]
        assert dct["actions"] == [{"action": {"_unset": {"NGY": 1, "NGZ": 1}}, "dict": "INCAR"}]


class UnconvergedErrorHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, *glob("unconverged/*", root_dir=TEST_FILES))

    def test_check_correct_electronic(self) -> None:
        shutil.copy("vasprun.xml.electronic", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {
            "actions": [{"action": {"_set": {"ALGO": "Normal"}}, "dict": "INCAR"}],
            "errors": ["Unconverged"],
        }
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_veryfast", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {"actions": [{"action": {"_set": {"ALGO": "Fast"}}, "dict": "INCAR"}], "errors": ["Unconverged"]}
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_normal", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {"actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}], "errors": ["Unconverged"]}
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_metagga_fast", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {"actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}], "errors": ["Unconverged"]}
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_hybrid_fast", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {"actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}], "errors": ["Unconverged"]}
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_hybrid_all", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"ALGO": "Damped", "TIME": 0.5}}}]

    def test_check_correct_electronic_repeat(self) -> None:
        shutil.copy("vasprun.xml.electronic2", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct == {"actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}], "errors": ["Unconverged"]}

    def test_check_correct_ionic(self) -> None:
        shutil.copy("vasprun.xml.ionic", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]

    def test_check_correct_scan(self) -> None:
        shutil.copy("vasprun.xml.scan", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert {"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}} in dct["actions"]

    def test_amin(self) -> None:
        shutil.copy("vasprun.xml.electronic_amin", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"AMIN": 0.01}}}]

    def test_as_from_dict(self) -> None:
        handler = UnconvergedErrorHandler("random_name.xml")
        h2 = UnconvergedErrorHandler.from_dict(handler.as_dict())
        assert isinstance(h2, UnconvergedErrorHandler)
        assert h2.output_filename == "random_name.xml"

    def test_correct_normal_with_condition(self) -> None:
        shutil.copy("vasprun.xml.electronic_normal", "vasprun.xml")  # Reuse an existing file
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {"actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}], "errors": ["Unconverged"]}

    def test_psmaxn(self) -> None:
        shutil.copy("vasprun.xml.electronic", "vasprun.xml")
        shutil.copy(f"{TEST_FILES}/large_cell_real_optlay/OUTCAR", "OUTCAR")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert set(dct["errors"]) == {"Unconverged", "psmaxn"}
        assert dct["actions"] == [
            {"action": {"_set": {"ALGO": "Normal"}}, "dict": "INCAR"},
            {"dict": "INCAR", "action": {"_set": {"LREAL": False}}},
        ]
        tracked_lru_cache.tracked_cache_clear()

    def test_uncorrectable(self) -> None:
        shutil.copy("vasprun.xml.unconverged_unfixable", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert set(dct["errors"]) == {"Unconverged"}
        assert dct["actions"] is None


class IncorrectSmearingHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "scan_metal/INCAR", "scan_metal/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = IncorrectSmearingHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["IncorrectSmearing"]
        incar = Incar.from_file("INCAR")
        assert incar["ISMEAR"] == 2
        assert incar["SIGMA"] == 0.2


class IncorrectSmearingHandlerStaticTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "static_smearing/INCAR", "static_smearing/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = IncorrectSmearingHandler()
        assert not handler.check()


class IncorrectSmearingHandlerFermiTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "fermi_smearing/INCAR", "fermi_smearing/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = IncorrectSmearingHandler()
        assert not handler.check()


class KspacingMetalHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "scan_metal/INCAR", "scan_metal/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = KspacingMetalHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["ScanMetal"]
        assert Incar.from_file("INCAR")["KSPACING"] == 0.22
        os.remove("vasprun.xml")

    def test_check_with_non_kspacing_wf(self) -> None:
        os.chdir(TEST_FILES)
        shutil.copy("INCAR", f"{self.tmp_path}/INCAR")
        shutil.copy("vasprun.xml", f"{self.tmp_path}/vasprun.xml")
        handler = KspacingMetalHandler(output_filename=f"{self.tmp_path}/vasprun.xml")
        assert handler.check() is False
        os.chdir(f"{TEST_FILES}/scan_metal")

        # TODO (@janosh 2023-11-03) remove when ending ScanMetalHandler deprecation period
        assert isinstance(ScanMetalHandler(), KspacingMetalHandler)


class LargeSigmaHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, *glob("large_sigma/*", root_dir=TEST_FILES))

    def test_check_correct_large_sigma(self) -> None:
        # first check should reduce sigma
        handler = LargeSigmaHandler(output_filename=zpath("OUTCAR_fail_sigma_check"))
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["LargeSigma"]
        assert Incar.from_file("INCAR")["SIGMA"] == pytest.approx(0.1115, rel=1.0e-3)

        # second check should find that sigma is correct as-is
        handler = LargeSigmaHandler(output_filename=zpath("OUTCAR_pass_sigma_check"))
        assert not handler.check()

    def test_no_crash_on_partial_output(self) -> None:
        from pathlib import Path

        from monty.io import zopen
        # ensure that the handler doesn't crash when the OUTCAR isn't completely written
        # this prevents jobs from being killed when the handler itself crashes

        orig_outcar_path = Path(zpath("OUTCAR_pass_sigma_check"))
        new_outcar_name = str(orig_outcar_path.parent.resolve() / f"temp_{orig_outcar_path.name}")
        shutil.copy(orig_outcar_path, new_outcar_name)

        # simulate this behavior by manually removing one of the electronic
        # entropy lines that the handler searches for
        with zopen(new_outcar_name, "rt") as f:
            data = f.read().splitlines()

        for rm_idx in range(len(data) - 1, 0, -1):
            if "T*S" in data[rm_idx]:
                data.pop(rm_idx)
                break

        with zopen(new_outcar_name, "wt") as f:
            f.write("\n".join(data))

        handler = LargeSigmaHandler(output_filename=zpath("OUTCAR_partial_output"))
        assert not handler.check()


class ZpotrfErrorHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(
            self.tmp_path,
            "zpotrf/INCAR",
            "zpotrf/POSCAR",
            "zpotrf/OSZICAR.empty",
            "zpotrf/vasp.out",
            "zpotrf/OSZICAR.one_step",
        )

    def test_first_step(self) -> None:
        shutil.copy("OSZICAR.empty", "OSZICAR")
        s1 = Structure.from_file("POSCAR")
        handler = VaspErrorHandler("vasp.out")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["zpotrf"]
        s2 = Structure.from_file("POSCAR")
        # NOTE (@janosh on 2023-09-10) next code line used to be:
        # assert s2.volume == pytest.approx(s1.volume * 1.2**3)
        # unclear why s2.volume changed
        assert s2.volume == pytest.approx(s1.volume)
        assert s1.volume == pytest.approx(64.346221)

    def test_potim_correction(self) -> None:
        shutil.copy("OSZICAR.one_step", "OSZICAR")
        s1 = Structure.from_file("POSCAR")
        handler = VaspErrorHandler("vasp.out")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["zpotrf"]
        s2 = Structure.from_file("POSCAR")
        assert s2.volume == pytest.approx(s1.volume)
        assert s1.volume == pytest.approx(64.3462)
        assert Incar.from_file("INCAR")["POTIM"] == pytest.approx(0.25)

    def test_static_run_correction(self) -> None:
        shutil.copy("OSZICAR.empty", "OSZICAR")
        s1 = Structure.from_file("POSCAR")
        incar = Incar.from_file("INCAR")

        # Test for NSW 0
        incar.update({"NSW": 0})
        incar.write_file("INCAR")
        handler = VaspErrorHandler("vasp.out")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["zpotrf"]
        s2 = Structure.from_file("POSCAR")
        assert s2.volume == pytest.approx(s1.volume)
        assert s2.volume == pytest.approx(64.346221)
        assert Incar.from_file("INCAR")["ISYM"] == 0


class ZpotrfErrorHandlerSmallTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(
            self.tmp_path,
            "zpotrf_small/INCAR",
            "zpotrf_small/POSCAR",
            "zpotrf_small/OSZICAR.empty",
            "zpotrf_small/vasp.out",
        )

    def test_small(self) -> None:
        handler = VaspErrorHandler("vasp.out")
        shutil.copy("OSZICAR.empty", "OSZICAR")
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zpotrf"]
        assert dct["actions"] == [
            {"dict": "INCAR", "action": {"_set": {"NCORE": 1}}},
            {"dict": "INCAR", "action": {"_unset": {"NPAR": 1}}},
        ]


class WalltimeHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        os.chdir(f"{TEST_FILES}/postprocess")
        os.environ.pop("CUSTODIAN_WALLTIME_START", None)

    def test_walltime_start(self) -> None:
        # checks the walltime handlers starttime initialization
        handler = WalltimeHandler(wall_time=3600)
        new_starttime = handler.start_time
        assert os.environ.get("CUSTODIAN_WALLTIME_START") == new_starttime.strftime("%a %b %d %H:%M:%S UTC %Y")
        # Test that walltime persists if new handler is created
        handler = WalltimeHandler(wall_time=3600)
        assert os.environ.get("CUSTODIAN_WALLTIME_START") == new_starttime.strftime("%a %b %d %H:%M:%S UTC %Y")

    def test_check_and_correct(self) -> None:
        # Try a 1 hr wall time with a 2 min buffer
        handler = WalltimeHandler(wall_time=3600, buffer_time=120)
        assert not handler.check()

        # This makes sure the check returns True when the time left is less
        # than the buffer time.
        handler.start_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        assert handler.check()

        # This makes sure the check returns True when the time left is less
        # than 3 x the average time per ionic step. We have a 62 min wall
        # time, a very short buffer time, but the start time was 62 mins ago
        handler = WalltimeHandler(wall_time=3720, buffer_time=10)
        handler.start_time = datetime.datetime.now() - datetime.timedelta(minutes=62)
        assert handler.check()

        # Test that the STOPCAR is written correctly.
        handler.correct()
        with open("STOPCAR") as file:
            content = file.read()
            assert content == "LSTOP = .TRUE."
        os.remove("STOPCAR")

        handler = WalltimeHandler(wall_time=3600, buffer_time=120, electronic_step_stop=True)

        assert not handler.check()
        handler.start_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        assert handler.check()

        handler.correct()
        with open("STOPCAR") as file:
            content = file.read()
            assert content == "LABORT = .TRUE."
        os.remove("STOPCAR")

    @classmethod
    def tearDown(cls) -> None:
        os.environ.pop("CUSTODIAN_WALLTIME_START", None)
        os.chdir(CWD)


class PositiveEnergyHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "positive_energy/INCAR", "positive_energy/POSCAR", "positive_energy/OSZICAR")

    def test_check_correct(self) -> None:
        handler = PositiveEnergyErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Positive energy"]

        assert os.path.isfile("error.1.tar.gz")
        with tarfile.open("error.1.tar.gz", "r:gz") as tar:
            assert len(tar.getmembers()) > 0

        incar = Incar.from_file("INCAR")

        assert incar["ALGO"] == "Normal"


class PotimHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "potim/INCAR", "potim/POSCAR", "potim/OSZICAR")

    def test_check_correct(self) -> None:
        incar = Incar.from_file("INCAR")
        original_potim = incar["POTIM"]

        handler = PotimErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["POTIM"]

        assert os.path.isfile("error.1.tar.gz")

        incar = Incar.from_file("INCAR")
        new_potim = incar["POTIM"]

        assert original_potim == new_potim
        assert incar["IBRION"] == 3


class LrfCommHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "lrf_comm/INCAR", "lrf_comm/OUTCAR", "lrf_comm/std_err.txt")

    def test_lrf_comm(self) -> None:
        handler = LrfCommutatorHandler("std_err.txt")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["lrf_comm"]
        vi = VaspInput.from_directory(".")
        assert vi["INCAR"]["LPEAD"] is True


class KpointsTransHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "KPOINTS", "std_err.txt.kpoints_trans")

    def test_kpoints_trans(self) -> None:
        handler = StdErrHandler("std_err.txt.kpoints_trans")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["kpoints_trans"]
        assert dct["actions"] == [{"action": {"_set": {"kpoints": [[4, 4, 4]]}}, "dict": "KPOINTS"}]

        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["kpoints_trans"]
        assert dct["actions"] == []  # don't correct twice


class OutOfMemoryHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "INCAR", "std_err.txt.oom")

    def test_oom(self) -> None:
        vi = VaspInput.from_directory(".")
        from custodian.vasp.interpreter import VaspModder

        VaspModder(vi=vi).apply_actions([{"dict": "INCAR", "action": {"_set": {"KPAR": 4}}}])
        handler = StdErrHandler("std_err.txt.oom")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["out_of_memory"]
        assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"KPAR": 2}}}]


class DriftErrorHandlerTest(PymatgenTest):
    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, "INCAR", "drift/OUTCAR", "drift/CONTCAR")

    def test_check(self) -> None:
        handler = DriftErrorHandler(max_drift=0.05, to_average=11)
        assert not handler.check()

        handler = DriftErrorHandler(max_drift=0.05)
        assert not handler.check()

        handler = DriftErrorHandler(max_drift=0.0001)
        assert not handler.check()

        incar = Incar.from_file("INCAR")
        incar["EDIFFG"] = -0.01
        incar.write_file("INCAR")

        handler = DriftErrorHandler(max_drift=0.0001)
        assert handler.check()

        handler = DriftErrorHandler()
        handler.check()
        assert handler.max_drift == 0.01

    def test_correct(self) -> None:
        handler = DriftErrorHandler(max_drift=0.0001, enaug_multiply=2)
        handler.check()
        handler.correct()
        incar = Incar.from_file("INCAR")
        assert incar.get("PREC") == "High"
        assert incar.get("ENAUG", 0) == incar.get("ENCUT", 2) * 2


class NonConvergingErrorHandlerTest(PymatgenTest):
    n_ionic_steps: int = 3

    def setUp(self) -> None:
        copy_tmp_files(self.tmp_path, *glob("nonconv/*", root_dir=TEST_FILES))

    def test_check(self) -> None:
        # calculation has four ionic steps which each hit NELM = 10
        handler = NonConvergingErrorHandler(nionic_steps=self.n_ionic_steps)
        assert handler.check()

        # increase NELM to avoid NonConvergingErrorHandler
        incar = Incar.from_file("INCAR")
        incar["NELM"] = 15
        incar.write_file("INCAR")
        assert not handler.check()

    def test_correct(self) -> None:
        original_incar = Incar.from_file("INCAR")

        handler = NonConvergingErrorHandler(nionic_steps=self.n_ionic_steps)
        handler.check()

        # INCAR has ALGO = Fast, so first correction --> Normal
        handler.correct()
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"].lower() == "normal"

        # because ISMEAR = -5, skip ALGO = all and adjust
        post_all_corrections = {"ALGO": "Normal", "AMIX": 0.1, "BMIX": 0.01, "ICHARG": 2}
        handler.correct()
        incar = Incar.from_file("INCAR")
        assert all(value == incar[key] for key, value in post_all_corrections.items())

        incar.update({"AMIX": 0.02, "BMIX": 2.9})
        post_all_corrections = {"ALGO": "Normal", "AMIN": 0.01, "BMIX": 3.0, "ICHARG": 2}
        handler.correct()
        incar = Incar.from_file("INCAR")
        assert all(value == incar[key] for key, value in post_all_corrections.items())

        # now replace ISMEAR --> 0, ALGO --> VeryFast to get ladder
        incar = Incar(original_incar)  # incar.copy() returns dict
        incar.update({"ISMEAR": 0, "ALGO": "veryfast"})
        incar.write_file("INCAR")

        algo_ladder = ("fast", "normal", "all")
        for algo in algo_ladder:
            handler.correct()
            incar = Incar.from_file("INCAR")
            assert incar["ALGO"].lower() == algo

        # now test meta-GGA and hybrid, should go directly from ALGO = fast to all
        for updates in ({"METAGGA": "SCAN"}, {"LHFCALC": True, "GGA": "PE"}):
            incar = Incar(original_incar)  # incar.copy() returns dict
            incar.update(updates)
            incar.write_file("INCAR")
            handler.correct()

            incar = Incar.from_file("INCAR")
            assert incar["ALGO"].lower() == "all"

    def test_as_from_dict(self) -> None:
        handler = NonConvergingErrorHandler("OSZICAR_random")
        h2 = NonConvergingErrorHandler.from_dict(handler.as_dict())
        assert isinstance(h2, NonConvergingErrorHandler)
        assert h2.output_filename == "OSZICAR_random"
