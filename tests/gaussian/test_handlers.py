import datetime
import glob
import gzip
import os
import shutil
from unittest import TestCase

from custodian.gaussian.handlers import GaussianErrorHandler, WallTimeErrorHandler
from tests.conftest import TEST_FILES

__author__ = "Rasha Atwi"
__version__ = "0.1"
__maintainer__ = "Rasha Atwi"
__email__ = "rasha.atwi@stonybrook.edu"
__status__ = "Alpha"
__date__ = "3/21/24"

TEST_DIR = f"{TEST_FILES}/gaussian"
SCR_DIR = f"{TEST_DIR}/scratch"
CWD = os.getcwd()


def gunzip_file(gauss_file):
    output_file = os.path.splitext(gauss_file)[0]
    if not os.path.exists(output_file) and os.path.exists(gauss_file):
        with gzip.open(gauss_file, "rb") as f_in, open(output_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return output_file


class TestGaussianErrorHandler(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        os.chdir(SCR_DIR)

    def test_opt_steps_cycles(self):
        gunzip_file(f"{TEST_DIR}/opt_steps_cycles.out.gz")
        for file in ["opt_steps_cycles.com", "opt_steps_cycles.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="opt_steps_cycles.com",
            output_file="opt_steps_cycles.out",
            opt_max_cycles=100,
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["opt_steps"]
        assert dct["actions"] == [
            {"structure": "from_final_structure"},
            {"opt_max_cycles": 100},
        ]

    def test_opt_steps_from_structure(self):
        gunzip_file(f"{TEST_DIR}/opt_steps_from_structure.out.gz")
        for file in ["opt_steps_from_structure.com", "opt_steps_from_structure.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="opt_steps_from_structure.com",
            output_file="opt_steps_from_structure.out",
            opt_max_cycles=5,
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["opt_steps"]
        assert dct["actions"] == [{"structure": "from_final_structure"}]

    def test_opt_steps_int_grid(self):
        gunzip_file(f"{TEST_DIR}/opt_steps_int_grid.out.gz")
        for file in ["opt_steps_int_grid.com", "opt_steps_int_grid.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="opt_steps_int_grid.com",
            output_file="opt_steps_int_grid.out",
            opt_max_cycles=1,
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["opt_steps"]
        assert dct["actions"] == [{"integral": "ultra_fine"}]

    def test_opt_steps_better_guess(self):
        gunzip_file(f"{TEST_DIR}/opt_steps_better_guess.out.gz")
        for file in ["opt_steps_better_guess.com", "opt_steps_better_guess.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="opt_steps_better_guess.com",
            output_file="opt_steps_better_guess.out",
            opt_max_cycles=1,
            lower_functional="HF",
            lower_basis_set="STO-3G",
            job_type="better_guess",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["opt_steps"]
        assert dct["actions"] == [{"opt_level_of_theory": "better_geom_guess"}]

        GaussianErrorHandler.activate_better_guess = False

    def test_scf_convergence_cycles(self):
        gunzip_file(f"{TEST_DIR}/scf_convergence_cycles.out.gz")
        for file in ["scf_convergence_cycles.com", "scf_convergence_cycles.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="scf_convergence_cycles.com",
            output_file="scf_convergence_cycles.out",
            scf_max_cycles=100,
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["scf_convergence"]
        assert dct["actions"] == [{"scf_max_cycles": 100}]

    def test_scf_convergence_algorithm(self):
        gunzip_file(f"{TEST_DIR}/scf_convergence_algorithm.out.gz")
        for file in ["scf_convergence_algorithm.com", "scf_convergence_algorithm.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="scf_convergence_algorithm.com",
            output_file="scf_convergence_algorithm.out",
            scf_max_cycles=1,
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["scf_convergence"]
        assert dct["actions"] == [{"scf_algorithm": "xqc"}]

    def test_scf_convergence_better_guess(self):
        gunzip_file(f"{TEST_DIR}/scf_convergence_better_guess.out.gz")
        for file in [
            "scf_convergence_better_guess.com",
            "scf_convergence_better_guess.out",
        ]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="scf_convergence_better_guess.com",
            output_file="scf_convergence_better_guess.out",
            scf_max_cycles=3,
            lower_functional="HF",
            lower_basis_set="STO-3G",
            job_type="better_guess",
        )
        handler.activate_better_guess = False
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["scf_convergence"]
        assert dct["actions"] == [{"scf_level_of_theory": "better_scf_guess"}]

        GaussianErrorHandler.activate_better_guess = False

    def test_linear_bend(self):
        gunzip_file(f"{TEST_DIR}/linear_bend.out.gz")
        for file in ["linear_bend.com", "linear_bend.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="linear_bend.com",
            output_file="linear_bend.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["linear_bend"]
        assert dct["actions"] == [{"coords": "rebuild_redundant_internals"}]

    def test_solute_solvent_surface(self):
        gunzip_file(f"{TEST_DIR}/solute_solvent_surface.out.gz")
        for file in ["solute_solvent_surface.com", "solute_solvent_surface.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="solute_solvent_surface.com",
            output_file="solute_solvent_surface.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["solute_solvent_surface"]
        assert dct["actions"] == [{"surface": "SAS"}]

    def test_internal_coords(self):
        pass

    def test_blank_line(self):
        gunzip_file(f"{TEST_DIR}/zmatrix.out.gz")
        for file in ["zmatrix.com", "zmatrix.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="zmatrix.com",
            output_file="zmatrix.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zmatrix"]
        assert dct["actions"] == [{"blank_lines": "rewrite_input_file"}]

    def test_missing_mol(self):
        gunzip_file(f"{TEST_DIR}/missing_mol.out.gz")
        for file in ["missing_mol.com", "missing_mol.out", "Optimization.chk"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="missing_mol.com",
            output_file="missing_mol.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["missing_mol"]
        assert dct["actions"] == [{"mol": "get_from_checkpoint"}]

    def test_found_coords(self):
        gunzip_file(f"{TEST_DIR}/found_coords.out.gz")
        for file in ["found_coords.com", "found_coords.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="found_coords.com",
            output_file="found_coords.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["found_coords"]
        assert dct["actions"] == [{"mol": "remove_from_input"}]

    def test_coords_dict_geom(self):
        gunzip_file(f"{TEST_DIR}/coords_dict_geom.out.gz")
        for file in ["coords_dict_geom.com", "coords_dict_geom.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="coords_dict_geom.com",
            output_file="coords_dict_geom.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["coords"]
        assert dct["actions"] == [{"coords": "remove_connectivity"}]

    def test_coords_string_geom(self):
        gunzip_file(f"{TEST_DIR}/coords_string_geom.out.gz")
        for file in ["coords_string_geom.com", "coords_string_geom.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="coords_string_geom.com",
            output_file="coords_string_geom.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["coords"]
        assert dct["actions"] == [{"coords": "remove_connectivity"}]

    def test_missing_file(self):
        gunzip_file(f"{TEST_DIR}/missing_file.out.gz")
        for file in ["missing_file.com", "missing_file.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="missing_file.com",
            output_file="missing_file.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["missing_file"]
        assert dct["actions"] is None

    def test_bad_file(self):
        gunzip_file(f"{TEST_DIR}/bad_file.out.gz")
        for file in ["bad_file.com", "bad_file.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="bad_file.com",
            output_file="bad_file.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["bad_file"]
        assert dct["actions"] is None

    def test_coord_inputs(self):
        gunzip_file(f"{TEST_DIR}/coord_inputs.out.gz")
        for file in ["coord_inputs.com", "coord_inputs.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="coord_inputs.com",
            output_file="coord_inputs.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["coord_inputs"]
        assert dct["actions"] == [{"coords": "use_zmatrix_format"}]

    def test_syntax(self):
        gunzip_file(f"{TEST_DIR}/syntax.out.gz")
        for file in ["syntax.com", "syntax.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="syntax.com",
            output_file="syntax.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["syntax"]
        assert dct["actions"] is None

    def test_insufficient_memory(self):
        gunzip_file(f"{TEST_DIR}/insufficient_memory.out.gz")
        for file in ["insufficient_memory.com", "insufficient_memory.out"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")
        handler = GaussianErrorHandler(
            input_file="insufficient_memory.com",
            output_file="insufficient_memory.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["insufficient_mem"]
        assert dct["actions"] == [{"memory": "increase_to_gaussian_recommendation"}]

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)
        files_to_remove = glob.glob(f"{TEST_DIR}/*.out")
        if files_to_remove and glob.glob(f"{TEST_DIR}/*.out.gz"):
            for file_path in files_to_remove:
                os.remove(file_path)


class TestWallTimeErrorHandler(TestCase):
    def setUp(self):
        os.makedirs(SCR_DIR)
        os.chdir(SCR_DIR)
        os.environ.pop("JOB_START_TIME", None)
        gunzip_file(f"{TEST_DIR}/walltime.out.gz")
        for file in ["walltime.com", "walltime.out", "Gau-mock.rwf"]:
            shutil.copyfile(f"{TEST_DIR}/{file}", f"{SCR_DIR}/{file}")

    def test_walltime_init(self):
        handler = WallTimeErrorHandler(
            wall_time=3600,
            buffer_time=300,
            input_file="wall_time.com",
            output_file="wall_time.out",
        )
        init_time = handler.init_time
        assert os.environ.get("JOB_START_TIME") == init_time.strftime("%a %b %d %H:%M:%S UTC %Y")
        # Test that walltime persists if new handler is created
        handler = WallTimeErrorHandler(
            wall_time=3600,
            buffer_time=300,
            input_file="walltime.com",
            output_file="walltime.out",
        )
        assert os.environ.get("JOB_START_TIME") == init_time.strftime("%a %b %d %H:%M:%S UTC %Y")

    def test_walltime_check_and_correct(self):
        # Try a 1 hr wall time with a 5 mins buffer
        handler = WallTimeErrorHandler(
            wall_time=3600,
            buffer_time=300,
            input_file="walltime.com",
            output_file="walltime.out",
        )
        assert not handler.check()

        # Make sure the check returns True when the remaining time is <= buffer time
        handler.init_time = datetime.datetime.now() - datetime.timedelta(minutes=59)
        assert handler.check()

        # Test that the input file is written correctly
        handler.correct()
        assert os.path.exists("walltime.com.wt")
        with open("walltime.com.wt") as file:
            first_line = file.readline().strip()
        # assert first_line == "%rwf=./Gau-mock.rwf"
        assert "rwf" in first_line

    def tearDown(self):
        os.chdir(CWD)
        shutil.rmtree(SCR_DIR)
        files_to_remove = glob.glob(f"{TEST_DIR}/*.out")
        if files_to_remove and glob.glob(f"{TEST_DIR}/*.out.gz"):
            for file_path in files_to_remove:
                os.remove(file_path)
