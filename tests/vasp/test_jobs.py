import glob
import multiprocessing
import os
import shutil
import unittest

import pymatgen
import pytest
from monty.os import cd
from monty.tempfile import ScratchDir
from pymatgen.io.vasp import Incar, Kpoints, Poscar

from custodian import ROOT
from custodian.vasp.jobs import GenerateVaspInputJob, VaspJob, VaspNEBJob

TEST_DIR = f"{ROOT}/tests/files"
pymatgen.core.SETTINGS["PMG_VASP_PSP_DIR"] = os.path.abspath(TEST_DIR)


class VaspJobTest(unittest.TestCase):
    def test_to_from_dict(self):
        v = VaspJob(["hello"])
        v2 = VaspJob.from_dict(v.as_dict())
        assert type(v2) == type(v)
        assert v2.vasp_cmd == ("hello",)

    def test_setup(self):
        with cd(TEST_DIR), ScratchDir(".", copy_from_current_on_enter=True):
            v = VaspJob(["hello"], auto_npar=True)
            v.setup()
            incar = Incar.from_file("INCAR")
            count = multiprocessing.cpu_count()
            # Need at least 3 CPUs for NPAR to be greater than 1
            if count > 3:
                assert incar["NPAR"] > 1

    def test_setup_run_no_kpts(self):
        # just make sure v.setup() and v.run() exit cleanly when no KPOINTS file is present
        with cd(os.path.join(TEST_DIR, "kspacing")), ScratchDir(".", copy_from_current_on_enter=True):
            v = VaspJob(["hello"], auto_npar=True)
            v.setup()
            with pytest.raises(FileNotFoundError):
                # a FileNotFoundError indicates that v.run() tried to run
                # subprocess.Popen(cmd, stdout=f_std, stderr=f_err) with
                # cmd == "hello", so it successfully parsed the input file
                # directory.
                v.run()

    def test_postprocess(self):
        with cd(os.path.join(TEST_DIR, "postprocess")), ScratchDir(".", copy_from_current_on_enter=True):
            shutil.copy("INCAR", "INCAR.backup")

            v = VaspJob(["hello"], final=False, suffix=".test", copy_magmom=True)
            v.postprocess()
            incar = Incar.from_file("INCAR")
            incar_prev = Incar.from_file("INCAR.test")

            for f in [
                "INCAR",
                "KPOINTS",
                "CONTCAR",
                "OSZICAR",
                "OUTCAR",
                "POSCAR",
                "vasprun.xml",
            ]:
                assert os.path.isfile(f"{f}.test")
                os.remove(f"{f}.test")
            shutil.move("INCAR.backup", "INCAR")

            assert incar["MAGMOM"] == pytest.approx([3.007, 1.397, -0.189, -0.189])
            assert incar_prev["MAGMOM"] == pytest.approx([5, -5, 0.6, 0.6])

    def test_continue(self):
        # Test the continuation functionality
        with cd(os.path.join(TEST_DIR, "postprocess")):
            # Test default functionality
            with ScratchDir(".", copy_from_current_on_enter=True):
                v = VaspJob("hello", auto_continue=True)
                v.setup()
                assert os.path.exists("continue.json"), "continue.json not created"
                v.setup()
                assert Poscar.from_file("CONTCAR").structure == Poscar.from_file("POSCAR").structure
                assert Incar.from_file("INCAR")["ISTART"] == 1
                v.postprocess()
                assert not os.path.exists("continue.json"), "continue.json not deleted after postprocessing"
            # Test explicit action functionality
            with ScratchDir(".", copy_from_current_on_enter=True):
                v = VaspJob(
                    ["hello"],
                    auto_continue=[{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}}],
                )
                v.setup()
                v.setup()
                assert Poscar.from_file("CONTCAR").structure != Poscar.from_file("POSCAR").structure
                assert Incar.from_file("INCAR")["ISTART"] == 1
                v.postprocess()

    def test_static(self):
        # Just a basic test of init.
        VaspJob.double_relaxation_run(["vasp"])


class VaspNEBJobTest(unittest.TestCase):
    def test_to_from_dict(self):
        v = VaspNEBJob(["hello"])
        v2 = VaspNEBJob.from_dict(v.as_dict())
        assert type(v2) == type(v)
        assert v2.vasp_cmd == ("hello",)

    def test_setup(self):
        with cd(os.path.join(TEST_DIR, "setup_neb")), ScratchDir(".", copy_from_current_on_enter=True):
            v = VaspNEBJob("hello", half_kpts=True)
            v.setup()

            incar = Incar.from_file("INCAR")
            count = multiprocessing.cpu_count()
            if count > 3:
                assert incar["NPAR"] > 1

            kpt = Kpoints.from_file("KPOINTS")
            kpt_pre = Kpoints.from_file("KPOINTS.orig")
            assert kpt_pre.style.name == "Monkhorst"
            assert kpt.style.name == "Gamma"

    def test_postprocess(self):
        neb_outputs = ["INCAR", "KPOINTS", "POTCAR", "vasprun.xml"]
        neb_sub_outputs = [
            "CHG",
            "CHGCAR",
            "CONTCAR",
            "DOSCAR",
            "EIGENVAL",
            "IBZKPT",
            "PCDAT",
            "POSCAR",
            "REPORT",
            "PROCAR",
            "OSZICAR",
            "OUTCAR",
            "WAVECAR",
            "XDATCAR",
        ]

        with cd(os.path.join(TEST_DIR, "postprocess_neb")):
            postprocess_neb = os.path.abspath(".")

            v = VaspNEBJob("hello", final=False, suffix=".test")
            v.postprocess()

            for f in neb_outputs:
                assert os.path.isfile(f"{f}.test")
                os.remove(f"{f}.test")

            sub_folders = glob.glob("[0-9][0-9]")
            for sf in sub_folders:
                os.chdir(os.path.join(postprocess_neb, sf))
                for f in neb_sub_outputs:
                    if os.path.exists(f):
                        assert os.path.isfile(f"{f}.test")
                        os.remove(f"{f}.test")


class GenerateVaspInputJobTest(unittest.TestCase):
    def test_run(self):
        with ScratchDir("."):
            for f in ["INCAR", "POSCAR", "POTCAR", "KPOINTS"]:
                shutil.copy(os.path.join("..", TEST_DIR, f), f)
            old_incar = Incar.from_file("INCAR")
            v = GenerateVaspInputJob("pymatgen.io.vasp.sets.MPNonSCFSet", contcar_only=False)
            v.run()
            incar = Incar.from_file("INCAR")
            assert incar["ICHARG"] == 11
            assert old_incar["ICHARG"] == 1
            kpoints = Kpoints.from_file("KPOINTS")
            assert str(kpoints.style) == "Reciprocal"
