import datetime as dt
import gzip
import json
import math
import os
import shutil
from types import SimpleNamespace
from unittest import TestCase

import pytest

from custodian.gaussian.handlers import GaussianErrorHandler, WallTimeErrorHandler
from tests.conftest import TEST_FILES

__author__ = "Rasha Atwi"
__version__ = "0.1"
__maintainer__ = "Rasha Atwi"
__email__ = "rasha.atwi@stonybrook.edu"
__status__ = "Alpha"
__date__ = "3/21/24"

TEST_DIR = f"{TEST_FILES}/gaussian"


def copy_input(file):
    """Copy a test file from TEST_DIR into the cwd, gunzipping it if only a .gz exists."""
    src = f"{TEST_DIR}/{file}"
    if os.path.exists(src):
        shutil.copyfile(src, file)
        return
    with gzip.open(f"{src}.gz", "rb") as f_in, open(file, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


class TestGaussianErrorHandler(TestCase):
    @pytest.fixture(autouse=True)
    def _run_in_tmp_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_opt_steps_cycles(self):
        for file in ["opt_steps_cycles.com", "opt_steps_cycles.out"]:
            copy_input(file)
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
        for file in ["opt_steps_from_structure.com", "opt_steps_from_structure.out"]:
            copy_input(file)
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
        for file in ["opt_steps_int_grid.com", "opt_steps_int_grid.out"]:
            copy_input(file)
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
        for file in ["opt_steps_better_guess.com", "opt_steps_better_guess.out"]:
            copy_input(file)
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
        for file in ["scf_convergence_cycles.com", "scf_convergence_cycles.out"]:
            copy_input(file)
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
        for file in ["scf_convergence_algorithm.com", "scf_convergence_algorithm.out"]:
            copy_input(file)
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
        for file in [
            "scf_convergence_better_guess.com",
            "scf_convergence_better_guess.out",
        ]:
            copy_input(file)
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
        for file in ["linear_bend.com", "linear_bend.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="linear_bend.com",
            output_file="linear_bend.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["linear_bend"]
        assert dct["actions"] == [{"coords": "rebuild_redundant_internals"}]

    def test_solute_solvent_surface(self):
        for file in ["solute_solvent_surface.com", "solute_solvent_surface.out"]:
            copy_input(file)
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
        for file in ["zmatrix.com", "zmatrix.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="zmatrix.com",
            output_file="zmatrix.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["zmatrix"]
        assert dct["actions"] == [{"blank_lines": "rewrite_input_file"}]

    def test_missing_mol(self):
        for file in ["missing_mol.com", "missing_mol.out", "Optimization.chk"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="missing_mol.com",
            output_file="missing_mol.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["missing_mol"]
        assert dct["actions"] == [{"mol": "get_from_checkpoint"}]

    def test_found_coords(self):
        for file in ["found_coords.com", "found_coords.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="found_coords.com",
            output_file="found_coords.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["found_coords"]
        assert dct["actions"] == [{"mol": "remove_from_input"}]

    def test_coords_dict_geom(self):
        for file in ["coords_dict_geom.com", "coords_dict_geom.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="coords_dict_geom.com",
            output_file="coords_dict_geom.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["coords"]
        assert dct["actions"] == [{"coords": "remove_connectivity"}]

    def test_coords_string_geom(self):
        for file in ["coords_string_geom.com", "coords_string_geom.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="coords_string_geom.com",
            output_file="coords_string_geom.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["coords"]
        assert dct["actions"] == [{"coords": "remove_connectivity"}]

    def test_missing_file(self):
        for file in ["missing_file.com", "missing_file.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="missing_file.com",
            output_file="missing_file.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["missing_file"]
        assert dct["actions"] is None

    def test_bad_file(self):
        for file in ["bad_file.com", "bad_file.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="bad_file.com",
            output_file="bad_file.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["bad_file"]
        assert dct["actions"] is None

    def test_coord_inputs(self):
        for file in ["coord_inputs.com", "coord_inputs.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="coord_inputs.com",
            output_file="coord_inputs.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["coord_inputs"]
        assert dct["actions"] == [{"coords": "use_zmatrix_format"}]

    def test_syntax(self):
        for file in ["syntax.com", "syntax.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="syntax.com",
            output_file="syntax.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["syntax"]
        assert dct["actions"] is None

    def test_insufficient_memory(self):
        for file in ["insufficient_memory.com", "insufficient_memory.out"]:
            copy_input(file)
        handler = GaussianErrorHandler(
            input_file="insufficient_memory.com",
            output_file="insufficient_memory.out",
        )
        handler.check()
        dct = handler.correct()
        assert dct["errors"] == ["insufficient_mem"]
        assert dct["actions"] == [{"memory": "increase_to_gaussian_recommendation"}]


class TestWallTimeErrorHandler(TestCase):
    @pytest.fixture(autouse=True)
    def _run_in_tmp_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("JOB_START_TIME", raising=False)
        for file in ["walltime.com", "walltime.out", "Gau-mock.rwf"]:
            copy_input(file)

    def test_walltime_init(self):
        handler = WallTimeErrorHandler(
            wall_time=3600,
            buffer_time=300,
            input_file="wall_time.com",
            output_file="wall_time.out",
        )
        init_time = handler.init_time
        assert os.environ.get("JOB_START_TIME") == f"{init_time:%a %b %d %H:%M:%S UTC %Y}"
        # Test that walltime persists if new handler is created
        handler = WallTimeErrorHandler(
            wall_time=3600,
            buffer_time=300,
            input_file="walltime.com",
            output_file="walltime.out",
        )
        assert os.environ.get("JOB_START_TIME") == f"{init_time:%a %b %d %H:%M:%S UTC %Y}"

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
        handler.init_time = dt.datetime.now() - dt.timedelta(minutes=59)
        assert handler.check()

        # Test that the input file is written correctly
        handler.correct()
        assert os.path.exists("walltime.com.wt")
        with open("walltime.com.wt") as file:
            first_line = file.readline().strip()
        # assert first_line == "%rwf=./Gau-mock.rwf"
        assert "rwf" in first_line


@pytest.fixture
def in_tmp_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(GaussianErrorHandler, "activate_better_guess", False)
    return tmp_path


def checked_handler(name: str, extra_files: tuple[str, ...] = (), **kwargs) -> GaussianErrorHandler:
    """Copy the <name>.com/.out fixtures into the cwd and return a handler after check()."""
    for file in (f"{name}.com", f"{name}.out", *extra_files):
        copy_input(file)
    handler = GaussianErrorHandler(input_file=f"{name}.com", output_file=f"{name}.out", **kwargs)
    handler.check()
    return handler


def assert_unfixable(handler: GaussianErrorHandler, name: str) -> None:
    """Run correct() and assert that no actions were taken and the input was not rewritten."""
    dct = handler.correct()
    assert dct["actions"] is None
    assert not os.path.exists(f"{name}.com.prev")


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        ({"Opt": {"MaxCycles": "5"}}, {"opt": {"maxcycles": "5"}}),
        ("SCF", "scf"),
        (["A", ("B", "c")], ["a", ["b", "c"]]),
        (5, 5),
        (None, None),
    ],
)
def test_recursive_lowercase(obj, expected):
    assert GaussianErrorHandler._recursive_lowercase(obj) == expected


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ({"int": "fine"}, ("int", "fine")),
        ({"integral": {"grid": "fine"}}, ("integral", {"grid": "fine"})),
        ({"opt": None}, ("", "")),
    ],
)
def test_int_keyword(route, expected):
    assert GaussianErrorHandler._int_keyword(route) == expected


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ({"int": "ultrafine"}, True),
        ({"integral": "99590"}, True),
        ({"int": "fine"}, False),
        ({"int": {"grid": "ultrafinegrid"}}, True),
        ({"int": {"ultrafine": None, "acc2e": "12"}}, True),
        ({"int": {"grid": "fine"}}, False),
        ({"int": {"acc2e": "12"}}, False),
        ({}, False),
    ],
)
def test_int_grid(route, expected):
    assert GaussianErrorHandler._int_grid(route) is expected


@pytest.mark.parametrize(
    ("route", "version", "changed", "expected_route"),
    [
        # no int keyword, G09: add int=ultrafine
        ({"opt": None}, "Gaussian 09", True, {"opt": None, "int": "ultrafine"}),
        # no int keyword, G16 (default grid is already ultrafine): no change
        ({"opt": None}, "Gaussian 16", False, {"opt": None}),
        # int=(grid=fine): replace grid
        ({"int": {"grid": "fine"}}, "Gaussian 16", True, {"int": {"grid": "ultrafine"}}),
        # int=(fine, acc2e=12): drop the named grid and set grid=ultrafine
        (
            {"int": {"fine": None, "acc2e": "12"}},
            "Gaussian 16",
            True,
            {"int": {"acc2e": "12", "grid": "ultrafine"}},
        ),
        # int=(75302, acc2e=12): numeric grid spec is also replaced
        (
            {"int": {"75302": None, "acc2e": "12"}},
            "Gaussian 16",
            True,
            {"int": {"acc2e": "12", "grid": "ultrafine"}},
        ),
        # integral=(acc2e=12) with no grid: only G09/G03 needs the change
        ({"integral": {"acc2e": "12"}}, "Gaussian 16", False, {"integral": {"acc2e": "12"}}),
        (
            {"integral": {"acc2e": "12"}},
            "Gaussian 09",
            True,
            {"integral": {"acc2e": "12", "grid": "ultrafine"}},
        ),
        # int=fine / int=75302 as plain strings
        ({"int": "fine"}, "Gaussian 16", True, {"int": "ultrafine"}),
        ({"int": "75302"}, "Gaussian 16", True, {"int": "ultrafine"}),
        # non-grid int option as a string
        ({"int": "nobasistransform"}, "Gaussian 16", False, {"int": "nobasistransform"}),
        (
            {"int": "nobasistransform"},
            "Gaussian 09",
            True,
            {"int": {"nobasistransform": None, "grid": "ultrafine"}},
        ),
        # already ultrafine: nothing to do
        ({"int": "ultrafine"}, "Gaussian 09", False, {"int": "ultrafine"}),
    ],
)
def test_add_int(route, version, changed, expected_route):
    handler = GaussianErrorHandler(input_file="dummy.com", output_file="dummy.out")
    handler.gin = SimpleNamespace(route_parameters=route)
    handler.gout = SimpleNamespace(version=version)
    assert handler._add_int() is changed
    assert handler.gin.route_parameters == expected_route


@pytest.mark.parametrize(
    ("name", "kwargs", "mutate", "check_correction"),
    [
        (
            "scf_convergence_cycles",
            {"scf_max_cycles": 100},
            None,
            lambda h: h.gin.route_parameters["scf"]["maxcycle"] == 100,
        ),
        (
            "scf_convergence_algorithm",
            {"scf_max_cycles": 1},
            None,
            lambda h: "xqc" in h.gin.route_parameters["scf"],
        ),
        (
            "opt_steps_cycles",
            {"opt_max_cycles": 100},
            None,
            lambda h: h.gin.route_parameters["opt"]["maxcycles"] == 100,
        ),
        (
            "opt_steps_int_grid",
            {"opt_max_cycles": 1},
            None,
            lambda h: h.gin.route_parameters["int"] == "ultrafine",
        ),
        (
            "linear_bend",
            {},
            None,
            lambda h: h.gin.route_parameters["geom"] == "(checkpoint, newdefinition)" and h.gin.molecule is None,
        ),
        (
            "solute_solvent_surface",
            {},
            None,
            lambda h: (
                h.gin.input_parameters["surface"] == "SAS"
                and h.gin.route_parameters["scrf"] == {"(solvent=generic,read)": None, "read": None}
            ),
        ),
        (
            "insufficient_memory",
            {},
            None,
            lambda h: h.gin.link0_parameters["%Mem"] == f"{math.ceil(h.recom_mem * 1.5)}MB",
        ),
        (
            "found_coords",
            {},
            None,
            lambda h: h.gin.molecule is None,
        ),
        (
            "coords_string_geom",
            {},
            None,
            lambda h: "geom" not in h.gin.route_parameters,
        ),
        (
            # geom=(connectivity, modredundant): only connectivity is dropped
            "coords_string_geom",
            {},
            lambda h: h.gin.route_parameters.update(geom={"connectivity": None, "modredundant": None}),
            lambda h: h.gin.route_parameters["geom"] == {"modredundant": None},
        ),
        (
            "coord_inputs",
            {},
            None,
            lambda h: h.cart_coords is False,
        ),
    ],
)
def test_correction_applied(in_tmp_path, name, kwargs, mutate, check_correction):
    handler = checked_handler(name, **kwargs)
    if mutate:
        mutate(handler)
    dct = handler.correct()
    assert dct["actions"]
    assert check_correction(handler)
    # original input is preserved and the corrected input is written
    assert os.path.exists(f"{name}.com.prev")
    assert os.path.exists(f"{name}.com")
    # a backup archive of the failed run is made
    assert os.path.exists("error.1.tar.gz")


def test_correct_copies_to_walltime_input(in_tmp_path):
    handler = checked_handler("scf_convergence_cycles", scf_max_cycles=100)
    with open("scf_convergence_cycles.com.wt", "w") as file:
        file.write("stale")
    handler.correct()
    with open("scf_convergence_cycles.com") as f1, open("scf_convergence_cycles.com.wt") as f2:
        assert f1.read() == f2.read()


@pytest.mark.parametrize(("job_type", "activated"), [("normal", False), ("better_guess", True)])
def test_scf_convergence_exhausted(in_tmp_path, monkeypatch, job_type, activated):
    # maxcycle already equals scf_max_cycles and xqc is already set
    handler = checked_handler("scf_convergence_better_guess", scf_max_cycles=3, job_type=job_type)
    monkeypatch.setattr(GaussianErrorHandler, "activate_better_guess", activated)
    assert_unfixable(handler, "scf_convergence_better_guess")


@pytest.mark.parametrize(("job_type", "activated"), [("normal", False), ("better_guess", True)])
def test_opt_steps_exhausted(in_tmp_path, monkeypatch, job_type, activated):
    # maxcycles already equals opt_max_cycles, the structure did not improve and
    # int=ultrafine is already set
    handler = checked_handler("opt_steps_better_guess", opt_max_cycles=1, job_type=job_type)
    monkeypatch.setattr(GaussianErrorHandler, "activate_better_guess", activated)
    assert_unfixable(handler, "opt_steps_better_guess")


def test_better_guess_switches_level_of_theory(in_tmp_path):
    handler = checked_handler(
        "scf_convergence_better_guess",
        scf_max_cycles=3,
        job_type="better_guess",
        lower_functional="HF",
        lower_basis_set="STO-3G",
    )
    handler.correct()
    assert handler.gin.functional == "HF"
    assert handler.gin.basis_set == "STO-3G"
    assert GaussianErrorHandler.activate_better_guess


def test_linear_bend_requires_chk(in_tmp_path):
    handler = checked_handler("linear_bend")
    del handler.gin.link0_parameters["%chk"]
    with pytest.raises(KeyError, match="CHK"):
        handler.correct()


def test_linear_bend_check_restores_prev_input(in_tmp_path):
    handler = checked_handler("linear_bend")
    with open("linear_bend.com") as file:
        original = file.read()
    handler.correct()
    with open("linear_bend.com") as file:
        assert file.read() != original
    # on the next check, the original input is restored from .prev
    handler.check()
    assert not os.path.exists("linear_bend.com.prev")
    with open("linear_bend.com") as file:
        assert file.read() == original


def test_solute_solvent_surface_already_sas(in_tmp_path):
    handler = checked_handler("solute_solvent_surface")
    handler.gin.input_parameters["Surface"] = "SAS"
    assert_unfixable(handler, "solute_solvent_surface")


@pytest.mark.parametrize(
    ("name", "expected_opt"),
    [
        # opt with no options
        ("zmatrix", "cartesian"),
        # opt=(z-matrix): z-matrix is replaced by cartesian
        ("coord_inputs", {"cartesian": None}),
    ],
)
def test_internal_coords(in_tmp_path, name, expected_opt):
    handler = checked_handler(name)
    handler.errors = {"internal_coords"}
    dct = handler.correct()
    assert dct["actions"] == [{"symmetry": False}, {"opt_cart_coords": True}]
    assert handler.gin.route_parameters["opt"] == expected_opt
    assert handler.gin.route_parameters["symmetry"] == "none"
    assert os.path.exists(f"{name}.com.prev")


@pytest.mark.parametrize("route_update", [{"opt": {"cartesian": None}}, {"opt": "cart"}])
def test_internal_coords_already_cartesian(in_tmp_path, route_update):
    handler = checked_handler("zmatrix")
    handler.errors = {"internal_coords"}
    handler.gin.route_parameters.update(route_update)
    assert_unfixable(handler, "zmatrix")


def test_internal_coords_no_opt(in_tmp_path):
    handler = checked_handler("zmatrix")
    handler.errors = {"internal_coords"}
    del handler.gin.route_parameters["opt"]
    assert_unfixable(handler, "zmatrix")


def test_zmatrix_blank_lines_present(in_tmp_path):
    handler = checked_handler("zmatrix")
    with open("zmatrix.com", "a") as file:
        file.write("\n\n")
    assert_unfixable(handler, "zmatrix")


def test_coords_no_connectivity(in_tmp_path):
    handler = checked_handler("coords_string_geom")
    handler.gin.route_parameters["geom"] = "check"
    assert_unfixable(handler, "coords_string_geom")


def test_found_coords_without_geom_check(in_tmp_path):
    handler = checked_handler("found_coords")
    del handler.gin.route_parameters["geom"]
    assert_unfixable(handler, "found_coords")


def test_coord_inputs_already_zmatrix(in_tmp_path):
    handler = checked_handler("coord_inputs", cart_coords=False)
    assert_unfixable(handler, "coord_inputs")


def test_missing_mol_without_chk(in_tmp_path):
    handler = checked_handler("missing_mol")
    with pytest.raises(FileNotFoundError, match="checkpoint"):
        handler.correct()


def test_missing_mol_with_geom_check(in_tmp_path):
    handler = checked_handler("missing_mol", extra_files=("Optimization.chk",))
    handler.gin.route_parameters["geom"] = "check"
    dct = handler.correct()
    assert dct == {"errors": ["missing_mol"], "actions": None}


@pytest.mark.parametrize("mem", ["100GB", None])
def test_insufficient_memory_unfixable(in_tmp_path, mem):
    handler = checked_handler("insufficient_memory")
    del handler.gin.link0_parameters["%Mem"]
    if mem:
        handler.gin.link0_parameters["%mem"] = mem
    dct = handler.correct()
    assert dct == {"errors": ["insufficient_mem"], "actions": None}


@pytest.mark.parametrize("error", ["charge", "empty_file"])
def test_unhandled_errors(in_tmp_path, error):
    handler = checked_handler("zmatrix")
    handler.errors = {error}
    dct = handler.correct()
    assert dct == {"errors": [error], "actions": None}


@pytest.mark.parametrize(
    ("mem", "expected"),
    [
        ("48GB", 48000),
        ("100mw", 763),
        ("1000000", 7.63),
        ("2tw", 2 * 7.63e6),
    ],
)
def test_find_dynamic_memory_allocated(mem, expected):
    key, dynamic_mem = GaussianErrorHandler._find_dynamic_memory_allocated({"%Mem": mem})
    assert key == "%Mem"
    assert dynamic_mem == pytest.approx(expected)


def test_find_dynamic_memory_allocated_missing():
    assert GaussianErrorHandler._find_dynamic_memory_allocated({"%chk": "a.chk"}) == (None, None)


def test_unfixable_errors_are_serializable(in_tmp_path):
    handler = checked_handler("solute_solvent_surface")
    handler.gin.input_parameters["Surface"] = "SAS"
    dct = handler.correct()
    assert dct["errors"] == ["solute_solvent_surface"]
    json.dumps(dct)


def test_coords_without_geom_keyword(in_tmp_path):
    handler = checked_handler("coords_string_geom")
    del handler.gin.route_parameters["geom"]
    assert_unfixable(handler, "coords_string_geom")


def test_missing_mol_without_guess_keyword(in_tmp_path):
    handler = checked_handler("missing_mol")
    del handler.gin.route_parameters["guess"]
    assert_unfixable(handler, "missing_mol")


@pytest.mark.parametrize("route_update", [{"nosymmetry": None}, {"symmetry": "none"}])
def test_internal_coords_symmetry_already_off(in_tmp_path, route_update):
    handler = checked_handler("zmatrix")
    handler.errors = {"internal_coords"}
    handler.gin.route_parameters.update(route_update)
    dct = handler.correct()
    assert dct["actions"] == [{"opt_cart_coords": True}]


@pytest.fixture
def run_elsewhere(tmp_path, monkeypatch):
    """A run directory that is not the cwd; returns (run_dir, cwd)."""
    (run_dir := tmp_path / "run").mkdir()
    (cwd := tmp_path / "cwd").mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(GaussianErrorHandler, "activate_better_guess", False)
    return run_dir, cwd


def copy_into(run_dir, *files):
    for file in files:
        copy_input(file)
        shutil.move(file, run_dir / file)


def test_convergence_plot_written_to_directory(run_elsewhere):
    run_dir, cwd = run_elsewhere
    copy_into(run_dir, "mol_opt.com", "mol_opt.out")
    GaussianErrorHandler(input_file="mol_opt.com", output_file="mol_opt.out").check(directory=str(run_dir))
    assert (run_dir / "convergence.png").exists()
    assert not (cwd / "convergence.png").exists()


def test_missing_mol_finds_chk_in_directory(run_elsewhere):
    run_dir, _ = run_elsewhere
    copy_into(run_dir, "missing_mol.com", "missing_mol.out", "Optimization.chk")
    handler = GaussianErrorHandler(input_file="missing_mol.com", output_file="missing_mol.out")
    handler.check(directory=str(run_dir))
    dct = handler.correct(directory=str(run_dir))
    assert dct["actions"] == [{"mol": "get_from_checkpoint"}]


@pytest.fixture
def walltime_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JOB_START_TIME", raising=False)
    for file in ["walltime.com", "walltime.out"]:
        copy_input(file)
    return tmp_path


def test_walltime_no_rwf(walltime_dir):
    handler = WallTimeErrorHandler(
        wall_time=3600, buffer_time=300, input_file="walltime.com", output_file="walltime.out"
    )
    dct = handler.correct()
    assert dct == {"errors": ["Walltime reached but not rwf file found"], "actions": None}
    assert not os.path.exists("walltime.com.wt")


def test_walltime_restart_input(walltime_dir):
    copy_input("Gau-mock.rwf")
    handler = WallTimeErrorHandler(wall_time=0, buffer_time=300, input_file="walltime.com", output_file="walltime.out")
    # wall_time=0 disables the check
    assert not handler.check()
    dct = handler.correct()
    assert dct == {"errors": ["wall_time_limit"], "actions": None}
    with open("walltime.com.wt") as file:
        lines = file.read().splitlines()
    assert lines[0] == "%rwf=Gau-mock.rwf"
    assert "%chk=Optimization.chk" in lines
    assert "%mem=48GB" in lines
    assert "#P Restart" in lines
