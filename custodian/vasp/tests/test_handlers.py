"""
Created on Jun 1, 2012
"""

__author__ = "Shyue Ping Ong, Stephen Dacek"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "Jun 1, 2012"

import datetime
import glob
import os
import shutil
import unittest

from pymatgen.io.vasp.inputs import Incar, Kpoints, Structure, VaspInput

from custodian.vasp.handlers import (
    AliasingErrorHandler,
    DriftErrorHandler,
    FrozenJobErrorHandler,
    IncorrectSmearingHandler,
    LargeSigmaHandler,
    LrfCommutatorHandler,
    MeshSymmetryErrorHandler,
    PositiveEnergyErrorHandler,
    PotimErrorHandler,
    ScanMetalHandler,
    StdErrHandler,
    UnconvergedErrorHandler,
    VaspErrorHandler,
    WalltimeHandler,
)

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_files")

cwd = os.getcwd()


def clean_dir():
    for f in glob.glob("error.*.tar.gz"):
        os.remove(f)
    for f in glob.glob("custodian.chk.*.tar.gz"):
        os.remove(f)


class VaspErrorHandlerTest(unittest.TestCase):
    def setUp(self):
        os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("KPOINTS", "KPOINTS.orig")
        shutil.copy("POSCAR", "POSCAR.orig")
        shutil.copy("CHGCAR", "CHGCAR.orig")

    def test_frozen_job(self):
        h = FrozenJobErrorHandler()
        d = h.correct()
        self.assertEqual(d["errors"], ["Frozen job"])
        self.assertEqual(Incar.from_file("INCAR")["ALGO"], "Normal")

    def test_subspace(self):
        h = VaspErrorHandler("vasp.subspace")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["subspacematrix"])
        self.assertEqual(d["actions"], [{"action": {"_set": {"LREAL": False}}, "dict": "INCAR"}])

        # 2nd error should set PREC to accurate.
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["subspacematrix"])
        self.assertEqual(d["actions"], [{"action": {"_set": {"PREC": "Accurate"}}, "dict": "INCAR"}])

    def test_check_correct(self):
        h = VaspErrorHandler("vasp.teterror")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["tet"])
        self.assertEqual(
            d["actions"],
            [{"action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}, "dict": "INCAR"}],
        )

        h = VaspErrorHandler("vasp.teterror", errors_subset_to_catch=["eddrmm"])
        self.assertFalse(h.check())

        h = VaspErrorHandler("vasp.sgrcon")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["rot_matrix"])
        self.assertEqual({a["dict"] for a in d["actions"]}, {"KPOINTS"})

        h = VaspErrorHandler("vasp.real_optlay")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["real_optlay"])
        self.assertEqual(d["actions"], [{"action": {"_set": {"LREAL": False}}, "dict": "INCAR"}])

    def test_mesh_symmetry(self):
        h = MeshSymmetryErrorHandler("vasp.ibzkpt")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["mesh_symmetry"])
        self.assertEqual(
            d["actions"],
            [{"action": {"_set": {"kpoints": [[4, 4, 4]]}}, "dict": "KPOINTS"}],
        )

    def test_brions(self):
        shutil.copy("INCAR.ibrion", "INCAR")
        h = VaspErrorHandler("vasp.brions")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["brions"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 1)
        self.assertAlmostEqual(i["POTIM"], 1.5)

        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["brions"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 2)
        self.assertAlmostEqual(i["POTIM"], 0.5)

    def test_dentet(self):
        h = VaspErrorHandler("vasp.dentet")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["dentet"])
        self.assertEqual(
            d["actions"],
            [{"action": {"_set": {"ISMEAR": 0, "SIGMA": 0.05}}, "dict": "INCAR"}],
        )

    def test_zbrent(self):
        h = VaspErrorHandler("vasp.zbrent")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["zbrent"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 2)
        self.assertEqual(i["EDIFF"], 1e-6)
        self.assertEqual(i["NELMIN"], 8)

        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["zbrent"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 1)
        self.assertEqual(i["EDIFF"], 1e-7)
        self.assertEqual(i["NELMIN"], 8)

        shutil.copy("INCAR.orig", "INCAR")
        h = VaspErrorHandler("vasp.zbrent")
        h.vtst_fixes = True
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["zbrent"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 3)
        self.assertEqual(i["IOPT"], 7)
        self.assertEqual(i["POTIM"], 0)
        self.assertEqual(i["EDIFF"], 1e-6)
        self.assertEqual(i["NELMIN"], 8)

        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["zbrent"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 3)
        self.assertEqual(i["IOPT"], 7)
        self.assertEqual(i["POTIM"], 0)
        self.assertEqual(i["EDIFF"], 1e-7)
        self.assertEqual(i["NELMIN"], 8)

        shutil.copy("INCAR.ediff", "INCAR")
        h = VaspErrorHandler("vasp.zbrent")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["zbrent"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 2)
        self.assertEqual(i["EDIFF"], 1e-7)
        self.assertEqual(i["NELMIN"], 8)

        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["zbrent"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["IBRION"], 1)
        self.assertEqual(i["EDIFF"], 1e-8)
        self.assertEqual(i["NELMIN"], 8)

    def test_brmix(self):
        h = VaspErrorHandler("vasp.brmix")
        self.assertEqual(h.check(), True)

        # The first (no good OUTCAR) correction, check IMIX
        d = h.correct()
        self.assertEqual(d["errors"], ["brmix"])
        vi = VaspInput.from_directory(".")
        self.assertEqual(vi["INCAR"]["IMIX"], 1)
        self.assertTrue(os.path.exists("CHGCAR"))

        # The next correction check Gamma and evenize
        h.correct()
        vi = VaspInput.from_directory(".")
        self.assertFalse("IMIX" in vi["INCAR"])
        self.assertTrue(os.path.exists("CHGCAR"))
        if vi["KPOINTS"].style == Kpoints.supported_modes.Gamma and vi["KPOINTS"].num_kpts < 1:
            all_kpts_even = all(n % 2 == 0 for n in vi["KPOINTS"].kpts[0])
            self.assertFalse(all_kpts_even)

        # The next correction check ISYM and no CHGCAR
        h.correct()
        vi = VaspInput.from_directory(".")
        self.assertEqual(vi["INCAR"]["ISYM"], 0)
        self.assertFalse(os.path.exists("CHGCAR"))

        shutil.copy("INCAR.nelect", "INCAR")
        h = VaspErrorHandler("vasp.brmix")
        self.assertEqual(h.check(), False)
        d = h.correct()
        self.assertEqual(d["errors"], [])

    def test_too_few_bands(self):
        os.chdir(os.path.join(test_dir, "too_few_bands"))
        shutil.copy("INCAR", "INCAR.orig")
        h = VaspErrorHandler("vasp.too_few_bands")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["too_few_bands"])
        self.assertEqual(d["actions"], [{"action": {"_set": {"NBANDS": 501}}, "dict": "INCAR"}])
        clean_dir()
        shutil.move("INCAR.orig", "INCAR")
        os.chdir(test_dir)

    def test_rot_matrix(self):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        subdir = os.path.join(test_dir, "poscar_error")
        os.chdir(subdir)
        shutil.copy("KPOINTS", "KPOINTS.orig")
        h = VaspErrorHandler()
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["rot_matrix"])
        os.remove(os.path.join(subdir, "error.1.tar.gz"))
        shutil.copy("KPOINTS.orig", "KPOINTS")
        os.remove("KPOINTS.orig")

    def test_rot_matrix_vasp6(self):
        h = VaspErrorHandler("vasp6.sgrcon")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["rot_matrix"])

    def test_to_from_dict(self):
        h = VaspErrorHandler("random_name")
        h2 = VaspErrorHandler.from_dict(h.as_dict())
        self.assertEqual(type(h2), type(h))
        self.assertEqual(h2.output_filename, "random_name")

    def test_pssyevx(self):
        h = VaspErrorHandler("vasp.pssyevx")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["pssyevx"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "Normal")

    def test_eddrmm(self):
        h = VaspErrorHandler("vasp.eddrmm")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["eddrmm"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "Normal")
        self.assertEqual(h.correct()["errors"], ["eddrmm"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["POTIM"], 0.25)

    def test_nicht_konv(self):
        h = VaspErrorHandler("vasp.nicht_konvergent")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["nicht_konv"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["LREAL"], False)

    def test_edddav(self):
        h = VaspErrorHandler("vasp.edddav")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["edddav"])
        self.assertFalse(os.path.exists("CHGCAR"))

    def test_algo_tet(self):
        h = VaspErrorHandler("vasp.algo_tet")
        self.assertEqual(h.check(), True)
        self.assertIn("algo_tet", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISMEAR"], 0)
        self.assertEqual(i["SIGMA"], 0.05)

    def test_gradient_not_orthogonal(self):
        h = VaspErrorHandler("vasp.gradient_not_orthogonal")
        self.assertEqual(h.check(), True)
        self.assertIn("grad_not_orth", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "Fast")

        shutil.copy("INCAR.gga_all", "INCAR")
        h = VaspErrorHandler("vasp.gradient_not_orthogonal")
        self.assertEqual(h.check(), True)
        self.assertIn("grad_not_orth", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "Fast")

        shutil.copy("INCAR.gga_ialgo53", "INCAR")
        h = VaspErrorHandler("vasp.gradient_not_orthogonal")
        self.assertEqual(h.check(), True)
        self.assertIn("grad_not_orth", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "Fast")
        self.assertNotIn("IALGO", i)

        shutil.copy("INCAR.hybrid_normal", "INCAR")
        h = VaspErrorHandler("vasp.gradient_not_orthogonal")
        self.assertEqual(h.check(), True)
        self.assertIn("grad_not_orth", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "Normal")

        shutil.copy("INCAR.hybrid_all", "INCAR")
        h = VaspErrorHandler("vasp.gradient_not_orthogonal")
        self.assertEqual(h.check(), True)
        self.assertIn("grad_not_orth", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "All")

        shutil.copy("INCAR.metagga_all", "INCAR")
        h = VaspErrorHandler("vasp.gradient_not_orthogonal")
        self.assertEqual(h.check(), True)
        self.assertIn("grad_not_orth", h.correct()["errors"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ALGO"], "All")

    def test_rhosyg(self):
        h = VaspErrorHandler("vasp.rhosyg")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["rhosyg"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["SYMPREC"], 1e-4)
        self.assertEqual(h.correct()["errors"], ["rhosyg"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISYM"], 0)

    def test_rhosyg_vasp6(self):
        h = VaspErrorHandler("vasp6.rhosyg")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["rhosyg"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["SYMPREC"], 1e-4)
        self.assertEqual(h.correct()["errors"], ["rhosyg"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISYM"], 0)

    def test_hnform(self):
        h = VaspErrorHandler("vasp.hnform")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["hnform"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISYM"], 0)

    def test_bravais(self):
        h = VaspErrorHandler("vasp6.bravais")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["bravais"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["SYMPREC"], 1e-4)

        shutil.copy("INCAR.symprec", "INCAR")
        h = VaspErrorHandler("vasp6.bravais")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["bravais"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["SYMPREC"], 1e-5)

    def test_posmap(self):
        h = VaspErrorHandler("vasp.posmap")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["posmap"])
        i = Incar.from_file("INCAR")
        self.assertAlmostEqual(i["SYMPREC"], 1e-6)

        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["posmap"])
        i = Incar.from_file("INCAR")
        self.assertAlmostEqual(i["SYMPREC"], 1e-4)

    def test_posmap_vasp6(self):
        h = VaspErrorHandler("vasp6.posmap")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["posmap"])
        i = Incar.from_file("INCAR")
        self.assertAlmostEqual(i["SYMPREC"], 1e-6)

        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["posmap"])
        i = Incar.from_file("INCAR")
        self.assertAlmostEqual(i["SYMPREC"], 1e-4)

    def test_point_group(self):
        h = VaspErrorHandler("vasp.point_group")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["point_group"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISYM"], 0)

    def test_symprec_noise(self):
        h = VaspErrorHandler("vasp.symprec_noise")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["symprec_noise"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["SYMPREC"], 1e-6)

    def test_dfpt_ncore(self):
        h = VaspErrorHandler("vasp.dfpt_ncore")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["dfpt_ncore"])
        incar = Incar.from_file("INCAR")
        self.assertTrue("NPAR" not in incar)
        self.assertTrue("NCORE" not in incar)

    def test_finite_difference_ncore(self):
        h = VaspErrorHandler("vasp.fd_ncore")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["dfpt_ncore"])
        incar = Incar.from_file("INCAR")
        self.assertTrue("NPAR" not in incar)
        self.assertTrue("NCORE" not in incar)

    def test_point_group_vasp6(self):
        # the error message is formatted differently in VASP6 compared to VASP5
        h = VaspErrorHandler("vasp6.point_group")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["point_group"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISYM"], 0)

    def test_inv_rot_matrix_vasp6(self):
        # the error message is formatted differently in VASP6 compared to VASP5
        h = VaspErrorHandler("vasp6.inv_rot_mat")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["inv_rot_mat"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["SYMPREC"], 1e-08)

    def test_bzint_vasp6(self):
        # the BZINT error message is formatted differently in VASP6 compared to VASP5
        h = VaspErrorHandler("vasp6.bzint")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["tet"])
        i = Incar.from_file("INCAR")
        self.assertEqual(i["ISMEAR"], 0)
        self.assertEqual(i["SIGMA"], 0.05)

    def test_too_large_kspacing(self):
        shutil.copy("INCAR.kspacing", "INCAR")
        vi = VaspInput.from_directory(".")
        h = VaspErrorHandler("vasp.teterror")
        h.check()
        d = h.correct()
        self.assertEqual(d["errors"], ["tet"])
        self.assertEqual(
            d["actions"],
            [
                {
                    "action": {"_set": {"KSPACING": vi["INCAR"].get("KSPACING") * 0.8}},
                    "dict": "INCAR",
                }
            ],
        )

    def test_nbands_not_sufficient(self):
        h = VaspErrorHandler("vasp.nbands_not_sufficient")
        self.assertEqual(h.check(), True)
        self.assertEqual(h.correct()["errors"], ["nbands_not_sufficient"])

    def test_too_few_bands_round_error(self):
        # originally there are  NBANDS= 7
        # correction should increase it
        shutil.copy("INCAR.too_few_bands_round_error", "INCAR")
        h = VaspErrorHandler("vasp.too_few_bands_round_error")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d['errors'], ["too_few_bands"])
        self.assertEqual(
            d["actions"],
            [{'dict': 'INCAR', 'action': {'_set': {'NBANDS': 8}}}]
        )

    def tearDown(self):
        os.chdir(test_dir)
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("CHGCAR.orig", "CHGCAR")
        clean_dir()
        os.chdir(cwd)


class AliasingErrorHandlerTest(unittest.TestCase):
    def setUp(self):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("KPOINTS", "KPOINTS.orig")
        shutil.copy("POSCAR", "POSCAR.orig")
        shutil.copy("CHGCAR", "CHGCAR.orig")

    def test_aliasing(self):
        os.chdir(os.path.join(test_dir, "aliasing"))
        shutil.copy("INCAR", "INCAR.orig")
        h = AliasingErrorHandler("vasp.aliasing")
        h.check()
        d = h.correct()
        shutil.move("INCAR.orig", "INCAR")
        clean_dir()
        os.chdir(test_dir)

        self.assertEqual(d["errors"], ["aliasing"])
        self.assertEqual(
            d["actions"],
            [
                {"action": {"_set": {"NGX": 34}}, "dict": "INCAR"},
                {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}},
                {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}},
            ],
        )

    def test_aliasing_incar(self):
        os.chdir(os.path.join(test_dir, "aliasing"))
        shutil.copy("INCAR", "INCAR.orig")
        h = AliasingErrorHandler("vasp.aliasing_incar")
        h.check()
        d = h.correct()

        self.assertEqual(d["errors"], ["aliasing_incar"])
        self.assertEqual(
            d["actions"],
            [
                {"action": {"_unset": {"NGY": 1, "NGZ": 1}}, "dict": "INCAR"},
                {"file": "CHGCAR", "action": {"_file_delete": {"mode": "actual"}}},
                {"file": "WAVECAR", "action": {"_file_delete": {"mode": "actual"}}},
            ],
        )

        incar = Incar.from_file("INCAR.orig")
        incar["ICHARG"] = 10
        incar.write_file("INCAR")
        d = h.correct()
        self.assertEqual(d["errors"], ["aliasing_incar"])
        self.assertEqual(
            d["actions"],
            [{"action": {"_unset": {"NGY": 1, "NGZ": 1}}, "dict": "INCAR"}],
        )

        shutil.move("INCAR.orig", "INCAR")
        clean_dir()
        os.chdir(test_dir)

    def tearDown(self):
        os.chdir(test_dir)
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("CHGCAR.orig", "CHGCAR")
        clean_dir()
        os.chdir(cwd)


class UnconvergedErrorHandlerTest(unittest.TestCase):
    def setUp(cls):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "unconverged")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("KPOINTS", "KPOINTS.orig")
        shutil.copy("POSCAR", "POSCAR.orig")
        shutil.copy("CONTCAR", "CONTCAR.orig")

    def test_check_correct_electronic(self):
        shutil.copy("vasprun.xml.electronic", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "Normal"}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )

        shutil.copy("vasprun.xml.electronic_veryfast", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "Fast"}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )

        shutil.copy("vasprun.xml.electronic_normal", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )

        shutil.copy("vasprun.xml.electronic_metagga_fast", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )

        shutil.copy("vasprun.xml.electronic_hybrid_fast", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )

        shutil.copy("vasprun.xml.electronic_hybrid_all", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "Damped", "TIME": 0.5}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )

        os.remove("vasprun.xml")

    def test_check_correct_electronic_repeat(self):
        shutil.copy("vasprun.xml.electronic2", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(
            d,
            {
                "actions": [{"action": {"_set": {"ALGO": "All"}}, "dict": "INCAR"}],
                "errors": ["Unconverged"],
            },
        )
        os.remove("vasprun.xml")

    def test_check_correct_ionic(self):
        shutil.copy("vasprun.xml.ionic", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        os.remove("vasprun.xml")

    def test_check_correct_scan(self):
        shutil.copy("vasprun.xml.scan", "vasprun.xml")
        h = UnconvergedErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Unconverged"])
        self.assertIn({"dict": "INCAR", "action": {"_set": {"ALGO": "All"}}}, d["actions"])
        os.remove("vasprun.xml")

    def test_to_from_dict(self):
        h = UnconvergedErrorHandler("random_name.xml")
        h2 = UnconvergedErrorHandler.from_dict(h.as_dict())
        self.assertEqual(type(h2), UnconvergedErrorHandler)
        self.assertEqual(h2.output_filename, "random_name.xml")

    @classmethod
    def tearDown(cls):
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("KPOINTS.orig", "KPOINTS")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("CONTCAR.orig", "CONTCAR")
        clean_dir()
        os.chdir(cwd)


class IncorrectSmearingHandlerTest(unittest.TestCase):
    def setUp(cls):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "scan_metal")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("vasprun.xml", "vasprun.xml.orig")

    def test_check_correct_scan_metal(self):
        h = IncorrectSmearingHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["IncorrectSmearing"])
        self.assertEqual(Incar.from_file("INCAR")["ISMEAR"], 2)
        self.assertEqual(Incar.from_file("INCAR")["SIGMA"], 0.2)
        os.remove("vasprun.xml")

    @classmethod
    def tearDown(cls):
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("vasprun.xml.orig", "vasprun.xml")
        clean_dir()
        os.chdir(cwd)


class IncorrectSmearingHandlerStaticTest(unittest.TestCase):
    def setUp(cls):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "static_smearing")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("vasprun.xml", "vasprun.xml.orig")

    def test_check_correct_scan_metal(self):
        h = IncorrectSmearingHandler()
        self.assertFalse(h.check())

    @classmethod
    def tearDown(cls):
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("vasprun.xml.orig", "vasprun.xml")
        clean_dir()
        os.chdir(cwd)


class IncorrectSmearingHandlerFermiTest(unittest.TestCase):
    def setUp(cls):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "fermi_smearing")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("vasprun.xml", "vasprun.xml.orig")

    def test_check_correct_scan_metal(self):
        h = IncorrectSmearingHandler()
        self.assertFalse(h.check())

    @classmethod
    def tearDown(cls):
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("vasprun.xml.orig", "vasprun.xml")
        clean_dir()
        os.chdir(cwd)


class ScanMetalHandlerTest(unittest.TestCase):
    def setUp(cls):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "scan_metal")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("vasprun.xml", "vasprun.xml.orig")

    def test_check_correct_scan_metal(self):
        h = ScanMetalHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["ScanMetal"])
        self.assertEqual(Incar.from_file("INCAR")["KSPACING"], 0.22)
        os.remove("vasprun.xml")

    @classmethod
    def tearDown(cls):
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("vasprun.xml.orig", "vasprun.xml")
        clean_dir()
        os.chdir(cwd)


class LargeSigmaHandlerTest(unittest.TestCase):
    def setUp(cls):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        subdir = os.path.join(test_dir, "large_sigma")
        os.chdir(subdir)

        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("vasprun.xml", "vasprun.xml.orig")

    def test_check_correct_large_sigma(self):
        h = LargeSigmaHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["LargeSigma"])
        self.assertEqual(Incar.from_file("INCAR")["SIGMA"], 1.44)
        os.remove("vasprun.xml")

    @classmethod
    def tearDown(cls):
        shutil.move("INCAR.orig", "INCAR")
        shutil.move("vasprun.xml.orig", "vasprun.xml")
        clean_dir()
        os.chdir(cwd)


class ZpotrfErrorHandlerTest(unittest.TestCase):
    def setUp(self):
        if "PMG_VASP_PSP_DIR" not in os.environ:
            os.environ["PMG_VASP_PSP_DIR"] = test_dir
        os.chdir(test_dir)
        os.chdir("zpotrf")
        shutil.copy("POSCAR", "POSCAR.orig")
        shutil.copy("INCAR", "INCAR.orig")

    def test_first_step(self):
        shutil.copy("OSZICAR.empty", "OSZICAR")
        s1 = Structure.from_file("POSCAR")
        h = VaspErrorHandler("vasp.out")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["zpotrf"])
        s2 = Structure.from_file("POSCAR")
        self.assertAlmostEqual(s2.volume, s1.volume * 1.2 ** 3, 3)

    def test_potim_correction(self):
        shutil.copy("OSZICAR.one_step", "OSZICAR")
        s1 = Structure.from_file("POSCAR")
        h = VaspErrorHandler("vasp.out")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["zpotrf"])
        s2 = Structure.from_file("POSCAR")
        self.assertAlmostEqual(s2.volume, s1.volume, 3)
        self.assertAlmostEqual(Incar.from_file("INCAR")["POTIM"], 0.25)

    def test_static_run_correction(self):
        shutil.copy("OSZICAR.empty", "OSZICAR")
        s1 = Structure.from_file("POSCAR")
        incar = Incar.from_file("INCAR")

        # Test for NSW 0
        incar.update({"NSW": 0})
        incar.write_file("INCAR")
        h = VaspErrorHandler("vasp.out")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["zpotrf"])
        s2 = Structure.from_file("POSCAR")
        self.assertAlmostEqual(s2.volume, s1.volume, 3)
        self.assertEqual(Incar.from_file("INCAR")["ISYM"], 0)

        # Test for ISIF 0-2
        incar.update({"NSW": 99, "ISIF": 2})
        incar.write_file("INCAR")
        h = VaspErrorHandler("vasp.out")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["zpotrf"])
        s2 = Structure.from_file("POSCAR")
        self.assertAlmostEqual(s2.volume, s1.volume, 3)
        self.assertEqual(Incar.from_file("INCAR")["ISYM"], 0)

    def tearDown(self):
        os.chdir(test_dir)
        os.chdir("zpotrf")
        shutil.move("POSCAR.orig", "POSCAR")
        shutil.move("INCAR.orig", "INCAR")
        os.remove("OSZICAR")
        clean_dir()
        os.chdir(cwd)


class WalltimeHandlerTest(unittest.TestCase):
    def setUp(self):
        os.chdir(os.path.join(test_dir, "postprocess"))
        if "CUSTODIAN_WALLTIME_START" in os.environ:
            os.environ.pop("CUSTODIAN_WALLTIME_START")

    def test_walltime_start(self):
        # checks the walltime handlers starttime initialization
        h = WalltimeHandler(wall_time=3600)
        new_starttime = h.start_time
        self.assertEqual(
            os.environ.get("CUSTODIAN_WALLTIME_START"),
            new_starttime.strftime("%a %b %d %H:%M:%S UTC %Y"),
        )
        # Test that walltime persists if new handler is created
        h = WalltimeHandler(wall_time=3600)
        self.assertEqual(
            os.environ.get("CUSTODIAN_WALLTIME_START"),
            new_starttime.strftime("%a %b %d %H:%M:%S UTC %Y"),
        )

    def test_check_and_correct(self):
        # Try a 1 hr wall time with a 2 min buffer
        h = WalltimeHandler(wall_time=3600, buffer_time=120)
        self.assertFalse(h.check())

        # This makes sure the check returns True when the time left is less
        # than the buffer time.
        h.start_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        self.assertTrue(h.check())

        # This makes sure the check returns True when the time left is less
        # than 3 x the average time per ionic step. We have a 62 min wall
        # time, a very short buffer time, but the start time was 62 mins ago
        h = WalltimeHandler(wall_time=3720, buffer_time=10)
        h.start_time = datetime.datetime.now() - datetime.timedelta(minutes=62)
        self.assertTrue(h.check())

        # Test that the STOPCAR is written correctly.
        h.correct()
        with open("STOPCAR") as f:
            content = f.read()
            self.assertEqual(content, "LSTOP = .TRUE.")
        os.remove("STOPCAR")

        h = WalltimeHandler(wall_time=3600, buffer_time=120, electronic_step_stop=True)

        self.assertFalse(h.check())
        h.start_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        self.assertTrue(h.check())

        h.correct()
        with open("STOPCAR") as f:
            content = f.read()
            self.assertEqual(content, "LABORT = .TRUE.")
        os.remove("STOPCAR")

    @classmethod
    def tearDown(cls):
        if "CUSTODIAN_WALLTIME_START" in os.environ:
            os.environ.pop("CUSTODIAN_WALLTIME_START")
        os.chdir(cwd)


class PositiveEnergyHandlerTest(unittest.TestCase):
    def setUp(cls):
        os.chdir(test_dir)

    def test_check_correct(self):
        subdir = os.path.join(test_dir, "positive_energy")
        os.chdir(subdir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("POSCAR", "POSCAR.orig")

        h = PositiveEnergyErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["Positive energy"])

        os.remove(os.path.join(subdir, "error.1.tar.gz"))

        incar = Incar.from_file("INCAR")

        shutil.move("INCAR.orig", "INCAR")
        shutil.move("POSCAR.orig", "POSCAR")

        self.assertEqual(incar["ALGO"], "Normal")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)


class PotimHandlerTest(unittest.TestCase):
    def setUp(cls):
        os.chdir(test_dir)

    def test_check_correct(self):
        subdir = os.path.join(test_dir, "potim")
        os.chdir(subdir)
        shutil.copy("INCAR", "INCAR.orig")
        shutil.copy("POSCAR", "POSCAR.orig")

        incar = Incar.from_file("INCAR")
        original_potim = incar["POTIM"]

        h = PotimErrorHandler()
        self.assertTrue(h.check())
        d = h.correct()
        self.assertEqual(d["errors"], ["POTIM"])

        os.remove(os.path.join(subdir, "error.1.tar.gz"))

        incar = Incar.from_file("INCAR")
        new_potim = incar["POTIM"]

        shutil.move("INCAR.orig", "INCAR")
        shutil.move("POSCAR.orig", "POSCAR")

        self.assertEqual(original_potim, new_potim)
        self.assertEqual(incar["IBRION"], 3)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cwd)


class LrfCommHandlerTest(unittest.TestCase):
    def setUp(self):
        os.chdir(test_dir)
        os.chdir("lrf_comm")
        for f in ["INCAR", "OUTCAR", "std_err.txt"]:
            shutil.copy(f, f + ".orig")

    def test_lrf_comm(self):
        h = LrfCommutatorHandler("std_err.txt")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["lrf_comm"])
        vi = VaspInput.from_directory(".")
        self.assertEqual(vi["INCAR"]["LPEAD"], True)

    def tearDown(self):
        os.chdir(test_dir)
        os.chdir("lrf_comm")
        for f in ["INCAR", "OUTCAR", "std_err.txt"]:
            shutil.move(f + ".orig", f)
        clean_dir()
        os.chdir(cwd)


class KpointsTransHandlerTest(unittest.TestCase):
    def setUp(self):
        os.chdir(test_dir)
        shutil.copy("KPOINTS", "KPOINTS.orig")

    def test_kpoints_trans(self):
        h = StdErrHandler("std_err.txt.kpoints_trans")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["kpoints_trans"])
        self.assertEqual(
            d["actions"],
            [{"action": {"_set": {"kpoints": [[4, 4, 4]]}}, "dict": "KPOINTS"}],
        )

        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["kpoints_trans"])
        self.assertEqual(d["actions"], [])  # don't correct twice

    def tearDown(self):
        shutil.move("KPOINTS.orig", "KPOINTS")
        clean_dir()
        os.chdir(cwd)


class OutOfMemoryHandlerTest(unittest.TestCase):
    def setUp(self):
        os.chdir(test_dir)
        shutil.copy("INCAR", "INCAR.orig")

    def test_oom(self):
        vi = VaspInput.from_directory(".")
        from custodian.vasp.interpreter import VaspModder

        VaspModder(vi=vi).apply_actions([{"dict": "INCAR", "action": {"_set": {"KPAR": 4}}}])
        h = StdErrHandler("std_err.txt.oom")
        self.assertEqual(h.check(), True)
        d = h.correct()
        self.assertEqual(d["errors"], ["out_of_memory"])
        self.assertEqual(d["actions"], [{"dict": "INCAR", "action": {"_set": {"KPAR": 2}}}])

    def tearDown(self):
        shutil.move("INCAR.orig", "INCAR")
        clean_dir()
        os.chdir(cwd)


class DriftErrorHandlerTest(unittest.TestCase):
    def setUp(self):
        os.chdir(os.path.abspath(test_dir))
        os.chdir("drift")

    def test_check(self):
        shutil.copy("INCAR", "INCAR.orig")

        h = DriftErrorHandler(max_drift=0.05, to_average=11)
        self.assertFalse(h.check())

        h = DriftErrorHandler(max_drift=0.05)
        self.assertFalse(h.check())

        h = DriftErrorHandler(max_drift=0.0001)
        self.assertFalse(h.check())

        incar = Incar.from_file("INCAR")
        incar["EDIFFG"] = -0.01
        incar.write_file("INCAR")

        h = DriftErrorHandler(max_drift=0.0001)
        self.assertTrue(h.check())

        h = DriftErrorHandler()
        h.check()
        self.assertEqual(h.max_drift, 0.01)

        clean_dir()
        shutil.move("INCAR.orig", "INCAR")

    def test_correct(self):
        shutil.copy("INCAR", "INCAR.orig")

        h = DriftErrorHandler(max_drift=0.0001, enaug_multiply=2)
        h.check()
        h.correct()
        incar = Incar.from_file("INCAR")
        self.assertTrue(incar.get("ADDGRID", False))

        h.correct()
        incar = Incar.from_file("INCAR")
        self.assertEqual(incar.get("PREC"), "High")
        self.assertEqual(incar.get("ENAUG", 0), incar.get("ENCUT", 2) * 2)

        clean_dir()
        shutil.move("INCAR.orig", "INCAR")

    def tearDown(self):
        clean_dir()
        os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
