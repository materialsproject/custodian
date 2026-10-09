"""Created on Jun 1, 2012."""

import datetime
import os
import re
import shutil
import tarfile
from glob import glob
from pathlib import Path
from types import SimpleNamespace

import pytest
from monty.io import zopen
from monty.os.path import zpath
from pymatgen.io.vasp.inputs import Incar, Kpoints, Structure, VaspInput
from pymatgen.symmetry.bandstructure import HighSymmKpath
from pymatgen.util.testing import MatSciTest

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
    _get_algo,
)
from custodian.vasp.interpreter import VaspModder
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


class VaspErrorHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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
        assert dct["actions"] == [{"action": {"_set": {"SYMPREC": 1.0e-6}}, "dict": "INCAR"}]

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
        assert dct["actions"] == [{"action": {"_set": {"generation_style": "Gamma"}}, "dict": "KPOINTS"}]
        kpoints = Kpoints.from_file("KPOINTS")
        assert kpoints.style == Kpoints.supported_modes.Gamma
        assert tuple(kpoints.kpts[0]) == (8, 2, 2)

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
        assert incar["ALGO"] == "Normal"

        shutil.copy("INCAR.metagga_all", "INCAR")
        handler = VaspErrorHandler("vasp.gradient_not_orthogonal")
        assert handler.check() is True
        assert "grad_not_orth" in handler.correct()["errors"]
        incar = Incar.from_file("INCAR")
        assert incar["ALGO"] == "Normal"

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
        assert incar["SYMPREC"] == 1e-6

        # SYMPREC already <= 1e-6 and ISYM unset: turn off symmetry (used to raise TypeError).
        incar.pop("ISYM", None)
        incar.write_file("INCAR")
        assert handler.check() is True
        assert handler.correct()["actions"] == [{"dict": "INCAR", "action": {"_set": {"ISYM": 0}}}]
        assert Incar.from_file("INCAR")["ISYM"] == 0

        shutil.copy("INCAR.symprec", "INCAR")
        handler = VaspErrorHandler("vasp6.bravais")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["bravais"]
        assert dct["actions"] == []  # SYMPREC = 1e-8 and ISYM = 0 already: unrecoverable

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
        assert Kpoints.from_file("KPOINTS").style == Kpoints.supported_modes.Gamma
        assert Incar.from_file("INCAR")["SYMPREC"] == 1e-5

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
        shutil.copy("OUTCAR_auto_nbands", "OUTCAR")
        assert handler.check() is True
        dct = handler.correct()
        assert "nbands_not_sufficient" in dct["errors"]
        # The OUTCAR fixture reports NBANDS= 64, more than the default (9). NBANDS must not be lowered,
        # and rerunning with the NBANDS that VASP already used would not help, so this is unrecoverable.
        assert dct["actions"] == []

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

    def test_harris(self) -> None:
        handler = VaspErrorHandler("vasp.harris")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["spin_polarized_harris"]
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

        # now ALGO = Normal with ISMEAR = -5: ALGO = All would trigger algo_tet, so no
        # actions (not even the CONTCAR copy) are returned and the error is unrecoverable
        shutil.copy("CONTCAR.eddiag", "CONTCAR")
        handler = VaspErrorHandler("vasp.eddiag")
        handler.check()
        dct = handler.correct()
        assert dct["actions"] == []

    def test_auto_nbands(self) -> None:
        # auto_nbands is only a warning and never fails the job.
        shutil.copy("OUTCAR_auto_nbands", "OUTCAR")
        handler = VaspErrorHandler(zpath("vasp.auto_nbands"))
        with pytest.warns(UserWarning, match="NBANDS seems to be too high"):
            assert handler.check() is False
        assert handler.errors == set()

    def test_auto_nbands_bad_parallelization(self, recwarn) -> None:
        shutil.copy("OUTCAR_auto_nbands_parallel", "OUTCAR")
        # hacky way to deal with custodian CI unzipping test files
        Incar.from_file(zpath("INCAR.auto_nbands_parallel")).write_file("INCAR")
        handler = VaspErrorHandler(zpath("vasp.auto_nbands"))
        assert handler.check() is False  # NBANDS = 64 < 2 * NELECT, so no warning either
        assert handler.errors == set()
        assert not [w for w in recwarn if "NBANDS" in str(w.message)]


class AliasingErrorHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class UnconvergedErrorHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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
        assert dct == {
            "actions": [{"action": {"_set": {"ALGO": "All", "ISEARCH": 1}}, "dict": "INCAR"}],
            "errors": ["Unconverged"],
        }
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_metagga_fast", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {
            "actions": [{"action": {"_set": {"ALGO": "All", "ISEARCH": 1}}, "dict": "INCAR"}],
            "errors": ["Unconverged"],
        }
        tracked_lru_cache.tracked_cache_clear()

        shutil.copy("vasprun.xml.electronic_hybrid_fast", "vasprun.xml")
        handler = UnconvergedErrorHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["Unconverged"]
        assert dct == {
            "actions": [{"action": {"_set": {"ALGO": "All", "ISEARCH": 1}}, "dict": "INCAR"}],
            "errors": ["Unconverged"],
        }
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
        assert dct == {
            "actions": [{"action": {"_set": {"ALGO": "All", "ISEARCH": 1}}, "dict": "INCAR"}],
            "errors": ["Unconverged"],
        }

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
        assert {"dict": "INCAR", "action": {"_set": {"ALGO": "All", "ISEARCH": 1}}} in dct["actions"]

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
        assert dct == {
            "actions": [{"action": {"_set": {"ALGO": "All", "ISEARCH": 1}}, "dict": "INCAR"}],
            "errors": ["Unconverged"],
        }

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


class IncorrectSmearingHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
        copy_tmp_files(self.tmp_path, "scan_metal/INCAR", "scan_metal/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = IncorrectSmearingHandler()
        assert handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["IncorrectSmearing"]
        incar = Incar.from_file("INCAR")
        assert incar["ISMEAR"] == 2
        assert incar["SIGMA"] == 0.2


class IncorrectSmearingHandlerStaticTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
        copy_tmp_files(self.tmp_path, "static_smearing/INCAR", "static_smearing/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = IncorrectSmearingHandler()
        assert not handler.check()


class IncorrectSmearingHandlerFermiTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
        copy_tmp_files(self.tmp_path, "fermi_smearing/INCAR", "fermi_smearing/vasprun.xml")

    def test_check_correct_scan_metal(self) -> None:
        handler = IncorrectSmearingHandler()
        assert not handler.check()


class KspacingMetalHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class LargeSigmaHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class ZpotrfErrorHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class ZpotrfErrorHandlerSmallTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class WalltimeHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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

    def test_check_with_malformed_outcar(self, tmp_path: Path) -> None:
        """Test that WalltimeHandler.check() returns False on malformed OUTCAR.

        This can happen when VASP is mid-write and the file contains incomplete
        data like a standalone '-' instead of a float. See
        https://github.com/materialsproject/pymatgen/issues/2251
        """
        os.chdir(tmp_path)

        # Create a malformed OUTCAR that would cause parsing to fail
        with open("OUTCAR", "w") as file:
            file.write("Free energy of the ion-electron system (eV)\n")
            file.write("  alpha Z        PSCENC =         -\n")  # incomplete value

        handler = WalltimeHandler(wall_time=3600, buffer_time=120)
        # Should return False (not crash) when OUTCAR parsing fails
        assert handler.check() is False

    @classmethod
    def tearDown(cls) -> None:
        os.environ.pop("CUSTODIAN_WALLTIME_START", None)
        os.chdir(CWD)


class PositiveEnergyHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class PotimHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class LrfCommHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
        copy_tmp_files(self.tmp_path, "lrf_comm/INCAR", "lrf_comm/OUTCAR", "lrf_comm/std_err.txt")

    def test_lrf_comm(self) -> None:
        handler = LrfCommutatorHandler("std_err.txt")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["lrf_comm"]
        vi = VaspInput.from_directory(".")
        assert vi["INCAR"]["LPEAD"] is True


class KpointsTransHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
        copy_tmp_files(self.tmp_path, "INCAR", "KPOINTS", "std_err.txt.kpoints_trans")

    def test_kpoints_trans(self) -> None:
        handler = StdErrHandler("std_err.txt.kpoints_trans")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["kpoints_trans"]
        assert dct["actions"] == [{"action": {"_set": {"ISYM": 0}}, "dict": "INCAR"}]

        assert handler.check() is True
        dct = handler.correct()
        assert dct["actions"] == []  # unrecoverable once symmetry is off

        incar = Incar.from_file("INCAR")
        assert incar["ENCUT"] == 520  # ENCUT is never changed
        assert incar["ISYM"] == 0
        kpoints = Kpoints.from_file("KPOINTS")
        assert kpoints.style == Kpoints.supported_modes.Monkhorst
        assert tuple(kpoints.kpts[0]) == (8, 2, 2)


GRAD_NOT_ORTH = "| EDWAV: internal error, the gradient is not orthogonal 2 1 -8.611e-4 |\n"


@pytest.mark.parametrize("algo", ["All", "Conjugate", "Damped", "Normal"])
@pytest.mark.parametrize("functional", [{}, {"METAGGA": "SCAN"}, {"LHFCALC": True}])
def test_stderr_gradient_not_orthogonal(tmp_path, algo, functional) -> None:
    """Without algo_tet: NBANDS first, then the ALGO fallback, then give up."""
    Incar({"ALGO": algo, "NBANDS": 40, **functional}).write_file(tmp_path / "INCAR")
    stderr = tmp_path / "std_err.txt"
    stderr.write_text(GRAD_NOT_ORTH)
    handler = StdErrHandler()
    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="TAUCAR"):
        result = handler.correct(directory=tmp_path)
    assert result["errors"] == ["grad_not_orth"]
    assert result["actions"] == [{"dict": "INCAR", "action": {"_set": {"NBANDS": 44}}}]
    incar = Incar.from_file(tmp_path / "INCAR")
    assert (incar["NBANDS"], incar["ALGO"]) == (44, algo)
    with tarfile.open(tmp_path / "error.1.tar.gz") as backup:
        assert "error.1/std_err.txt" in backup.getnames()

    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="TAUCAR"):
        result = handler.correct(directory=tmp_path)
    expected_algo = "Normal" if functional or algo == "Normal" else "Fast"
    assert result["actions"] == (
        [] if algo == "Normal" else [{"dict": "INCAR", "action": {"_set": {"ALGO": expected_algo}}}]
    )
    incar = Incar.from_file(tmp_path / "INCAR")
    assert (incar["NBANDS"], incar["ALGO"]) == (44, expected_algo)

    # Unrecoverable: no further changes, even if ALGO was switched back by another handler.
    Incar({**incar, "ALGO": algo}).write_file(tmp_path / "INCAR")
    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="TAUCAR"):
        assert handler.correct(directory=tmp_path)["actions"] == []

    stderr.write_text("")
    assert not handler.check(directory=tmp_path)
    assert handler.errors == set()


def test_stderr_gradient_not_orthogonal_nbands_from_outcar(tmp_path) -> None:
    """NBANDS is read from the OUTCAR when it is not set in the INCAR."""
    Incar({"ALGO": "All"}).write_file(tmp_path / "INCAR")
    shutil.copy(f"{TEST_FILES}/OUTCAR_auto_nbands", tmp_path / "OUTCAR")
    (tmp_path / "std_err.txt").write_text(GRAD_NOT_ORTH)
    handler = StdErrHandler()
    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="AOCC"):
        result = handler.correct(directory=tmp_path)
    assert result["actions"] == [{"dict": "INCAR", "action": {"_set": {"NBANDS": 70}}}]


def test_gradient_not_orthogonal_without_nbands(tmp_path) -> None:
    """If NBANDS cannot be determined, go straight to the ALGO fallback, then give up."""
    Incar({"ALGO": "All"}).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text(GRAD_NOT_ORTH)
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="Intel-compiled VASP on AMD"):
        result = handler.correct(directory=tmp_path)
    assert result["actions"] == [{"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}}]
    assert handler.error_count["grad_not_orth"] == 1

    Incar({"ALGO": "All"}).write_file(tmp_path / "INCAR")
    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="TAUCAR"):
        result = handler.correct(directory=tmp_path)
    assert result["actions"] == [{"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}}]

    Incar({"ALGO": "All"}).write_file(tmp_path / "INCAR")
    assert handler.check(directory=tmp_path)
    with pytest.warns(UserWarning, match="TAUCAR"):
        assert handler.correct(directory=tmp_path)["actions"] == []


class OutOfMemoryHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
        copy_tmp_files(self.tmp_path, "INCAR", "std_err.txt.oom")

    def test_oom(self) -> None:
        vi = VaspInput.from_directory(".")

        VaspModder(vi=vi).apply_actions([{"dict": "INCAR", "action": {"_set": {"KPAR": 4}}}])
        handler = StdErrHandler("std_err.txt.oom")
        assert handler.check() is True
        dct = handler.correct()
        assert dct["errors"] == ["out_of_memory"]
        assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"KPAR": 2}}}]


class DriftErrorHandlerTest(MatSciTest):
    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


class NonConvergingErrorHandlerTest(MatSciTest):
    n_ionic_steps: int = 3

    @pytest.fixture(autouse=True)
    def _setup(self, _tmp_dir) -> None:
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


KPOINTS_TRANS_MSG = "internal error in GENERATE_KPOINTS_TRANS: number of G-vector changed in star\n"
MESH_SYMMETRY_MSG = "Reciprocal lattice and k-lattice belong to different class of lattices.\n"


def test_kpoints_trans_kspacing(tmp_path) -> None:
    """kpoints_trans with KSPACING (no KPOINTS file) also goes to ISYM = 0."""
    Incar({"KSPACING": 0.3}).write_file(tmp_path / "INCAR")
    (tmp_path / "std_err.txt").write_text(KPOINTS_TRANS_MSG)
    handler = StdErrHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct == {"errors": ["kpoints_trans"], "actions": [{"dict": "INCAR", "action": {"_set": {"ISYM": 0}}}]}
    assert handler.check(directory=tmp_path)
    assert handler.correct(directory=tmp_path)["actions"] == []


@pytest.mark.parametrize("encut", [None, 450])
@pytest.mark.parametrize("isym", [0, -1])
def test_kpoints_trans_symmetry_off(tmp_path, isym, encut) -> None:
    """With symmetry already off, kpoints_trans is unrecoverable; ENCUT and KPOINTS are never touched."""
    incar = Incar({"ISYM": isym} if encut is None else {"ISYM": isym, "ENCUT": encut})
    incar.write_file(tmp_path / "INCAR")
    Kpoints.monkhorst_automatic((8, 8, 1)).write_file(tmp_path / "KPOINTS")
    (tmp_path / "std_err.txt").write_text(KPOINTS_TRANS_MSG)
    handler = StdErrHandler()
    assert handler.check(directory=tmp_path)
    assert handler.correct(directory=tmp_path)["actions"] == []
    assert tuple(Kpoints.from_file(tmp_path / "KPOINTS").kpts[0]) == (8, 8, 1)
    assert Incar.from_file(tmp_path / "INCAR") == incar


def test_mesh_symmetry_slab_mp_to_gamma(tmp_path) -> None:
    """A slab-like 8x8x1 MP mesh becomes Gamma 8x8x1, not a uniform 4x4x4 mesh."""
    Incar({"ISYM": 2}).write_file(tmp_path / "INCAR")
    Kpoints.monkhorst_automatic((8, 8, 1)).write_file(tmp_path / "KPOINTS")
    (tmp_path / "vasp.out").write_text(MESH_SYMMETRY_MSG)
    handler = MeshSymmetryErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "KPOINTS", "action": {"_set": {"generation_style": "Gamma"}}}]
    kpoints = Kpoints.from_file(tmp_path / "KPOINTS")
    assert kpoints.style == Kpoints.supported_modes.Gamma
    assert tuple(kpoints.kpts[0]) == (8, 8, 1)
    assert Incar.from_file(tmp_path / "INCAR")["ISYM"] == 2


def test_mesh_symmetry_gamma_to_isym0(tmp_path) -> None:
    """An already Gamma-centred mesh is kept and symmetry is switched off instead."""
    Incar({"ISYM": 2}).write_file(tmp_path / "INCAR")
    Kpoints.gamma_automatic((8, 8, 1)).write_file(tmp_path / "KPOINTS")
    (tmp_path / "vasp.out").write_text(MESH_SYMMETRY_MSG)
    handler = MeshSymmetryErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"ISYM": 0}}}]
    assert Incar.from_file(tmp_path / "INCAR")["ISYM"] == 0
    assert tuple(Kpoints.from_file(tmp_path / "KPOINTS").kpts[0]) == (8, 8, 1)
    assert not handler.check(directory=tmp_path)


def test_mesh_symmetry_isym_off_no_action(tmp_path) -> None:
    """With a Gamma mesh and symmetry already off there is nothing left to change."""
    Incar({"ISYM": 0}).write_file(tmp_path / "INCAR")
    Kpoints.gamma_automatic((8, 8, 1)).write_file(tmp_path / "KPOINTS")
    (tmp_path / "vasp.out").write_text(MESH_SYMMETRY_MSG)
    assert MeshSymmetryErrorHandler().correct(directory=tmp_path)["actions"] is None


def test_mesh_symmetry_line_mode(tmp_path) -> None:
    """Explicit k-point lists are left alone; symmetry is switched off instead."""
    Incar({"ISYM": 2}).write_file(tmp_path / "INCAR")
    Kpoints.automatic_linemode(2, HighSymmKpath(Structure.from_file(f"{TEST_FILES}/POSCAR"))).write_file(
        tmp_path / "KPOINTS"
    )
    (tmp_path / "vasp.out").write_text(MESH_SYMMETRY_MSG)
    handler = MeshSymmetryErrorHandler()
    assert handler.check(directory=tmp_path)
    assert handler.correct(directory=tmp_path)["actions"] == [{"dict": "INCAR", "action": {"_set": {"ISYM": 0}}}]
    assert Kpoints.from_file(tmp_path / "KPOINTS").style == Kpoints.supported_modes.Line_mode


@pytest.mark.parametrize(
    ("functional", "expected_algo"),
    [({}, "Fast"), ({"METAGGA": "R2scan"}, "Normal"), ({"LHFCALC": True}, "Normal")],
)
def test_algo_tet_with_grad_not_orth(tmp_path, functional, expected_algo) -> None:
    """algo_tet and grad_not_orth must agree on the fallback ALGO; no ALGO = Fast for meta-GGAs/hybrids."""
    Incar({"ALGO": "All", "ISMEAR": -5, **functional}).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text(
        "ALGO=A and IALGO=5X tend to fail with the tetrahedron method\n"
        "EDWAV: internal error, the gradient is not orthogonal\n"
    )
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    assert handler.errors == {"algo_tet", "grad_not_orth"}
    dct = handler.correct(directory=tmp_path)
    assert {a["action"]["_set"]["ALGO"] for a in dct["actions"]} == {expected_algo}
    assert Incar.from_file(tmp_path / "INCAR")["ALGO"] == expected_algo


def test_algo_tet_with_grad_not_orth_keeps_nbands_ladder(tmp_path) -> None:
    """A co-occurring algo_tet only changes ALGO and does not consume the NBANDS step."""
    Incar({"ALGO": "All", "ISMEAR": -5, "NBANDS": 20}).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text("ALGO=A and IALGO=5X tend to fail with the tetrahedron method\n" + GRAD_NOT_ORTH)
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"ALGO": "Fast"}}}] * 2
    assert handler.error_count["grad_not_orth"] == 0

    (tmp_path / "vasp.out").write_text(GRAD_NOT_ORTH)
    assert handler.check(directory=tmp_path)
    assert handler.errors == {"grad_not_orth"}
    with pytest.warns(UserWarning, match="TAUCAR"):
        dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"NBANDS": 22}}}]


def test_brmix_kspacing_ladder(tmp_path) -> None:
    """With KSPACING, KGAMMA is set once and the ladder then advances to ISYM = 0."""
    Incar({"KSPACING": 0.3, "KGAMMA": False}).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text("BRMIX: very serious problems\n")
    handler = VaspErrorHandler()
    handler.error_count["brmix"] = 2
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"KGAMMA": True}}}]
    assert handler.error_count["brmix"] == 3

    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert {"dict": "INCAR", "action": {"_set": {"ISYM": 0}}} in dct["actions"]
    assert {"dict": "INCAR", "action": {"_set": {"KGAMMA": True}}} not in dct["actions"]
    assert handler.error_count["brmix"] == 4


def test_brmix_no_outcar_skips_rerun(tmp_path) -> None:
    """Without a valid OUTCAR the ISTART = 1 rerun is skipped (does not rely on assert)."""
    Incar({"ISMEAR": 0}).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text("BRMIX: very serious problems\n")
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"IMIX": 1}}}]


def _write_vasprun(src: str, dest: Path, algo: str) -> None:
    with zopen(zpath(f"{TEST_FILES}/unconverged/{src}"), mode="rt", encoding="utf-8") as file:
        text = file.read()
    text = re.sub(r'(<i type="string" name="ALGO">)\s*\w+', rf"\1 {algo}", text, count=1)
    dest.write_text(text)


def test_unconverged_metagga_already_all(tmp_path) -> None:
    """A meta-GGA already on ALGO = All moves on to the mixing fallback instead of re-setting ALGO = All."""
    _write_vasprun("vasprun.xml.electronic_metagga_fast", tmp_path / "vasprun.xml", "All")
    handler = UnconvergedErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"]
    assert all(a["action"]["_set"].get("ALGO") != "All" for a in dct["actions"])


def test_unconverged_hybrid_damped_no_ping_pong(tmp_path) -> None:
    """A hybrid already on ALGO = Damped must not be switched back to ALGO = All."""
    _write_vasprun("vasprun.xml.electronic_hybrid_all", tmp_path / "vasprun.xml", "Damped")
    handler = UnconvergedErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert all(a["action"]["_set"].get("ALGO") != "All" for a in dct["actions"] or [])


def test_potim_check_uses_directory(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    shutil.copytree(f"{TEST_FILES}/potim", run_dir)
    monkeypatch.chdir(tmp_path)  # no POSCAR in cwd
    assert PotimErrorHandler().check(directory=str(run_dir))


def test_nonconverging_hybrid_damped_not_switched_to_all(tmp_path) -> None:
    """NonConvergingErrorHandler must not move a hybrid from ALGO = Damped back to All."""
    shutil.copytree(f"{TEST_FILES}/nonconv", tmp_path, dirs_exist_ok=True)
    incar = Incar.from_file(tmp_path / "INCAR")
    incar.update({"LHFCALC": True, "ALGO": "Damped", "ISMEAR": 0})
    incar.write_file(tmp_path / "INCAR")
    dct = NonConvergingErrorHandler(nionic_steps=3).correct(directory=str(tmp_path))
    assert all(a["action"]["_set"].get("ALGO") != "All" for a in dct["actions"] or [])


def test_potim_unrecoverable_when_damped_md_with_tiny_potim(tmp_path) -> None:
    """IBRION = 3 with POTIM < 0.1 has nothing left to try; inputs are left untouched."""
    shutil.copytree(f"{TEST_FILES}/potim", tmp_path, dirs_exist_ok=True)
    incar = Incar.from_file(tmp_path / "INCAR")
    incar.update({"IBRION": 3, "POTIM": 0.05})
    incar.write_file(tmp_path / "INCAR")
    handler = PotimErrorHandler()
    assert handler.check(directory=str(tmp_path))
    dct = handler.correct(directory=str(tmp_path))
    assert dct == {"errors": ["POTIM"], "actions": None}
    assert Incar.from_file(tmp_path / "INCAR") == incar
    assert not glob(f"{tmp_path}/error.*.tar.gz")


def _setup_frozen_job(tmp_path: Path, incar_params: dict) -> Incar:
    for fname in ("INCAR", "KPOINTS", "POSCAR", "POTCAR"):
        shutil.copy(f"{TEST_FILES}/{fname}", tmp_path / fname)
    incar = Incar.from_file(tmp_path / "INCAR")
    incar.update({"ALGO": "Normal", **incar_params})
    incar.write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text("")
    return incar


def test_frozen_job_restarts_from_contcar(tmp_path) -> None:
    """An ionic run that is not on ALGO = Fast restarts from CONTCAR to keep ionic progress."""
    incar = _setup_frozen_job(tmp_path, {"NSW": 10})
    contcar = Structure.from_file(tmp_path / "POSCAR")
    contcar.perturb(0.05)
    contcar.to(filename=str(tmp_path / "CONTCAR"), fmt="poscar")

    dct = FrozenJobErrorHandler().correct(directory=str(tmp_path))
    assert dct == {
        "errors": ["Frozen job"],
        "actions": [{"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}],
    }
    assert (tmp_path / "POSCAR").read_text() == (tmp_path / "CONTCAR").read_text()
    assert Incar.from_file(tmp_path / "INCAR") == incar
    assert glob(f"{tmp_path}/error.*.tar.gz")


@pytest.mark.parametrize(("nsw", "write_contcar"), [(0, True), (10, False)])
def test_frozen_job_unrecoverable(tmp_path, nsw, write_contcar) -> None:
    """Static runs, or ionic runs without a valid CONTCAR, are unrecoverable once ALGO is not Fast."""
    incar = _setup_frozen_job(tmp_path, {"NSW": nsw})
    poscar = (tmp_path / "POSCAR").read_text()
    if write_contcar:
        shutil.copy(f"{TEST_FILES}/CONTCAR", tmp_path / "CONTCAR")

    dct = FrozenJobErrorHandler().correct(directory=str(tmp_path))
    assert dct == {"errors": ["Frozen job"], "actions": None}
    assert Incar.from_file(tmp_path / "INCAR") == incar
    assert (tmp_path / "POSCAR").read_text() == poscar
    assert not glob(f"{tmp_path}/error.*.tar.gz")


def test_inv_rot_mat_ladder(tmp_path) -> None:
    """inv_rot_mat: MP -> Gamma mesh, then SYMPREC up to 1e-4, then ISYM = 0, then unrecoverable."""
    Incar({"ISMEAR": 0}).write_file(tmp_path / "INCAR")
    Kpoints.monkhorst_automatic((4, 4, 4)).write_file(tmp_path / "KPOINTS")
    (tmp_path / "vasp.out").write_text("rotation matrix was not found (increase SYMPREC)\n")
    handler = VaspErrorHandler()

    expected = [
        [{"dict": "KPOINTS", "action": {"_set": {"generation_style": "Gamma"}}}],
        [{"dict": "INCAR", "action": {"_set": {"SYMPREC": 1e-4}}}],
        [{"dict": "INCAR", "action": {"_set": {"ISYM": 0}}}],
        [],
    ]
    for step, actions in enumerate(expected, start=1):
        assert handler.check(directory=tmp_path)
        assert handler.correct(directory=tmp_path)["actions"] == actions
        assert handler.error_count["inv_rot_mat"] == step
    assert Kpoints.from_file(tmp_path / "KPOINTS").style == Kpoints.supported_modes.Gamma
    incar = Incar.from_file(tmp_path / "INCAR")
    assert incar["SYMPREC"] == pytest.approx(1e-4)
    assert incar["ISYM"] == 0


@pytest.mark.parametrize(("symprec", "expected"), [(1e-6, 1e-5), (1e-5, 1e-4), (5e-5, 1e-4)])
def test_inv_rot_mat_kspacing_symprec(tmp_path, symprec, expected) -> None:
    """Without a KPOINTS file, inv_rot_mat goes straight to increasing SYMPREC (x10, capped at 1e-4)."""
    Incar({"KSPACING": 0.3, "SYMPREC": symprec}).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text("rotation matrix was not found (increase SYMPREC)\n")
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"SYMPREC": expected}}}]


@pytest.mark.parametrize(
    ("incar", "expected"),
    [
        ({"ALGO": "F"}, "fast"),
        ({"ALGO": "n"}, "normal"),
        ({"ALGO": "V"}, "veryfast"),
        ({"ALGO": "A"}, "all"),
        ({"ALGO": "Conjugate"}, "all"),
        ({"ALGO": "D"}, "damped"),
        ({"ALGO": "Exact"}, "exact"),
        ({"ALGO": "None"}, "none"),
        ({"ALGO": "Nothing"}, "nothing"),
        ({"ALGO": "Eigenval"}, "eigenval"),
        ({"ALGO": "CHI"}, "chi"),
        ({"ALGO": "ACFDT"}, "acfdt"),
        ({}, "normal"),
        ({"IALGO": 48}, "veryfast"),
        ({"IALGO": 68}, "fast"),
        ({"IALGO": 58}, "all"),
        ({"IALGO": 53}, "damped"),
    ],
)
def test_get_algo(incar, expected) -> None:
    assert _get_algo(Incar(incar)) == expected


def _setup_error_run(tmp_path: Path, incar: dict, message: str) -> None:
    for name in ("KPOINTS", "POSCAR"):
        shutil.copy(f"{TEST_FILES}/{name}", tmp_path / name)
    Incar(incar).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text(f"{message}\n")


@pytest.mark.parametrize(
    ("algo", "message", "expected"),
    [
        ("F", "WARNING in EDDRMM: call to ZHEGV failed", "Normal"),
        ("V", "WARNING in EDDRMM: call to ZHEGV failed", "Normal"),
        ("F", "ERROR EDDIAG: Call to routine ZHEEV failed!", "Normal"),
    ],
)
def test_vasp_error_handler_abbreviated_algo(tmp_path, algo, message, expected) -> None:
    """Abbreviated ALGO values (only the first letter matters in VASP) trigger the same corrections."""
    _setup_error_run(tmp_path, {"ALGO": algo}, message)
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert {"dict": "INCAR", "action": {"_set": {"ALGO": expected}}} in dct["actions"]


@pytest.mark.parametrize(
    ("algo", "message"),
    [("A", "Error EDDDAV: Call to ZHEGV failed"), ("N", "ERROR in subspace rotation PSSYEVX")],
)
def test_vasp_error_handler_abbreviated_algo_unchanged(tmp_path, algo, message) -> None:
    """ALGO = A is already All (edddav) and ALGO = N is already Normal (pssyevx), so ALGO is not re-set."""
    _setup_error_run(tmp_path, {"ALGO": algo}, message)
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert all("ALGO" not in a["action"].get("_set", {}) for a in dct["actions"] if "dict" in a)


@pytest.mark.parametrize(("algo", "expected"), [("V", "Fast"), ("F", "Normal")])
def test_nonconverging_abbreviated_algo(tmp_path, algo, expected) -> None:
    shutil.copytree(f"{TEST_FILES}/nonconv", tmp_path, dirs_exist_ok=True)
    incar = Incar.from_file(tmp_path / "INCAR")
    incar.update({"ALGO": algo, "ISMEAR": 0})
    incar.write_file(tmp_path / "INCAR")
    dct = NonConvergingErrorHandler(nionic_steps=3).correct(directory=str(tmp_path))
    assert dct["actions"] == [{"dict": "INCAR", "action": {"_set": {"ALGO": expected}}}]


@pytest.mark.parametrize(("algo", "expected"), [("V", "Fast"), ("F", "Normal")])
def test_unconverged_abbreviated_algo(tmp_path, algo, expected) -> None:
    _write_vasprun("vasprun.xml.electronic_veryfast", tmp_path / "vasprun.xml", algo)
    handler = UnconvergedErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert {"dict": "INCAR", "action": {"_set": {"ALGO": expected}}} in dct["actions"]


def _nbands_correction(tmp_path: Path, monkeypatch, incar: dict, outcar_nbands: int | None = None) -> int:
    """Return the NBANDS set for nbands_not_sufficient with NELECT = 40 and the 8-ion test POSCAR."""
    _setup_error_run(tmp_path, incar, "The number of bands is not sufficient to hold all electrons.")
    if outcar_nbands is not None:
        (tmp_path / "OUTCAR").write_text(f"   number of bands    NBANDS=     {outcar_nbands}\n")
    monkeypatch.setattr("custodian.vasp.handlers.load_outcar", lambda _path: SimpleNamespace(nelect=40.0))
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    assert "nbands_not_sufficient" in handler.errors
    dct = handler.correct(directory=tmp_path)
    return next(a["action"]["_set"]["NBANDS"] for a in dct["actions"] if "NBANDS" in a["action"].get("_set", {}))


@pytest.mark.parametrize("ncl_tag", ["LSORBIT", "LNONCOLLINEAR"])
def test_nbands_not_sufficient_noncollinear(tmp_path, monkeypatch, ncl_tag) -> None:
    """The collinear default is max(NINT(40 + 2) / 2 + max(8 / 2, 3), INT(0.6 * 40)) = 25; doubled if noncollinear."""
    assert _nbands_correction(tmp_path, monkeypatch, {"ISPIN": 1}) == 25
    assert _nbands_correction(tmp_path, monkeypatch, {"ISPIN": 1, ncl_tag: True}) == 50


def test_nbands_not_sufficient_spin_polarized(tmp_path, monkeypatch) -> None:
    """ISPIN = 2 adds floor((sum(MAGMOM) + 1) / 2) bands: 4 for the default 1 muB on each of 8 ions."""
    assert _nbands_correction(tmp_path, monkeypatch, {"ISPIN": 2}) == 29
    assert _nbands_correction(tmp_path, monkeypatch, {"ISPIN": 2, "MAGMOM": [5.0] * 8}) == 45


@pytest.mark.parametrize(("incar_nbands", "outcar_nbands"), [(200, None), (200, 160)])
def test_nbands_not_sufficient_never_lowers(tmp_path, monkeypatch, incar_nbands, outcar_nbands) -> None:
    nbands = _nbands_correction(tmp_path, monkeypatch, {"ISPIN": 1, "NBANDS": incar_nbands}, outcar_nbands)
    assert nbands == incar_nbands


@pytest.mark.parametrize("incar_nbands", [None, 120])
def test_nbands_not_sufficient_no_increase_unrecoverable(tmp_path, monkeypatch, incar_nbands) -> None:
    """If NBANDS cannot be increased beyond what VASP already used (160), there is nothing to try."""
    incar = {"ISPIN": 1} if incar_nbands is None else {"ISPIN": 1, "NBANDS": incar_nbands}
    with pytest.raises(StopIteration):
        _nbands_correction(tmp_path, monkeypatch, incar, outcar_nbands=160)


_CONTCAR_COPY = {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}


@pytest.mark.parametrize(
    ("incar", "expected"),
    [
        ({"ALGO": "VeryFast"}, {"ALGO": "Normal"}),
        ({"ALGO": "F"}, {"ALGO": "Normal"}),
        ({"ALGO": "N", "ISMEAR": 0}, {"ALGO": "All", "ISEARCH": 1}),
        ({"ALGO": "Normal", "ISMEAR": 0}, {"ALGO": "All", "ISEARCH": 1}),
        ({}, {"ALGO": "All", "ISEARCH": 1}),  # defaults: ALGO = Normal, ISMEAR = 1
    ],
)
@pytest.mark.parametrize("error", ["zheev", "eddiag"])
def test_zheev_eddiag_algo_escalation(tmp_path, incar, expected, error) -> None:
    """ALGO is escalated VeryFast/Fast -> Normal -> All, never to the expensive ALGO = Exact."""
    shutil.copy(f"{TEST_FILES}/CONTCAR.eddiag", tmp_path / "CONTCAR")
    Incar(incar).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text(f"{VaspErrorHandler.error_msgs[error][0]}\n")
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == [_CONTCAR_COPY, {"dict": "INCAR", "action": {"_set": expected}}]


@pytest.mark.parametrize(
    "incar",
    [
        {"ALGO": "Normal", "ISMEAR": -5},  # ALGO = All with tetrahedron smearing triggers algo_tet
        {"ALGO": "All"},
        {"ALGO": "Conjugate"},
        {"ALGO": "Damped"},
        {"ALGO": "Exact"},
    ],
)
def test_zheev_eddiag_unrecoverable(tmp_path, incar) -> None:
    """With no ALGO change available, no actions (not even the CONTCAR copy) are returned."""
    shutil.copy(f"{TEST_FILES}/CONTCAR.eddiag", tmp_path / "CONTCAR")
    Incar(incar).write_file(tmp_path / "INCAR")
    (tmp_path / "vasp.out").write_text(f"{VaspErrorHandler.error_msgs['eddiag'][0]}\n")
    handler = VaspErrorHandler()
    assert handler.check(directory=tmp_path)
    dct = handler.correct(directory=tmp_path)
    assert dct["actions"] == []
