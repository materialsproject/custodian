from __future__ import annotations

import sys
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pymatgen.io.vasp import Incar, Kpoints
from pymatgen.io.vasp import sets as vasp_sets

from custodian.vasp.handlers import (
    MeshSymmetryErrorHandler,
    NonConvergingErrorHandler,
    PotimErrorHandler,
    UnconvergedErrorHandler,
    VaspErrorHandler,
)
from custodian.vasp.jobs import VaspJob
from custodian.vasp.validators import VasprunXMLValidator
from tests.cli.conftest import import_cli

run_vasp = import_cli("run_vasp")

CONTCAR_COPY = {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
DEFAULT_HANDLERS = [
    "VaspErrorHandler",
    "MeshSymmetryErrorHandler",
    "UnconvergedErrorHandler",
    "NonConvergingErrorHandler",
    "PotimErrorHandler",
]


def make_args(jobs, **kwargs) -> Namespace:
    params = {"command": "mpirun -np 4 vasp", "no_auto_npar": False, "static_kpoint": 1} | kwargs
    return Namespace(jobs=jobs, **params)


def kpoints_actions(settings):
    return [s for s in settings if s.get("dict") == "KPOINTS"]


class TestLoadClass:
    def test_no_params(self) -> None:
        handler = run_vasp.load_class("custodian.vasp.handlers", "VaspErrorHandler")
        assert isinstance(handler, VaspErrorHandler)
        assert handler.output_filename == "vasp.out"

    def test_params_are_yaml_decoded(self) -> None:
        handler = run_vasp.load_class("custodian.vasp.handlers", "NonConvergingErrorHandler?nionic_steps=5")
        assert isinstance(handler, NonConvergingErrorHandler)
        assert handler.nionic_steps == 5
        assert isinstance(handler.nionic_steps, int)

    def test_multiple_params(self) -> None:
        handler = run_vasp.load_class(
            "custodian.vasp.handlers", "MeshSymmetryErrorHandler?output_filename=my.out,output_vasprun=my.xml"
        )
        assert handler.output_filename == "my.out"
        assert handler.output_vasprun == "my.xml"

    def test_validator(self) -> None:
        assert isinstance(run_vasp.load_class("custodian.vasp.validators", "VasprunXMLValidator"), VasprunXMLValidator)

    def test_bad_spec_exits(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            run_vasp.load_class("custodian.vasp.handlers", "VaspErrorHandler?a=1?b=2")
        assert exc.value.code == -1
        assert "Bad handler specification" in capsys.readouterr().out


@pytest.mark.usefixtures("vasp_dir")
class TestGetJobs:
    def test_double_relax(self) -> None:
        jobs = list(run_vasp.get_jobs(make_args(["relax", "relax"])))
        assert len(jobs) == 2
        assert all(isinstance(j, VaspJob) for j in jobs)
        assert [j.suffix for j in jobs] == [".relax1", ".relax2"]
        assert [j.final for j in jobs] == [False, True]
        assert [j.backup for j in jobs] == [True, False]
        assert jobs[0].vasp_cmd == ("mpirun", "-np", "4", "vasp")
        assert jobs[0].settings_override == []
        assert jobs[1].settings_override == [CONTCAR_COPY]
        assert all(j.auto_npar for j in jobs)
        assert not any(j.copy_magmom for j in jobs)

    def test_explicit_numbered_suffix(self) -> None:
        jobs = list(run_vasp.get_jobs(make_args(["relax5", "relax6", "relax"])))
        assert [j.suffix for j in jobs] == [".relax5", ".relax6", ".relax3"]

    def test_no_auto_npar(self) -> None:
        jobs = list(run_vasp.get_jobs(make_args(["relax", "relax"], no_auto_npar=True)))
        assert not any(j.auto_npar for j in jobs)

    @pytest.mark.parametrize(("multiplier", "expected"), [(1, [8, 2, 2]), (2, [16, 4, 4])])
    def test_static(self, multiplier, expected) -> None:
        jobs = list(run_vasp.get_jobs(make_args(["relax", "static"], static_kpoint=multiplier)))
        assert jobs[1].suffix == ".static2"
        assert jobs[1].settings_override == [
            CONTCAR_COPY,
            {"dict": "INCAR", "action": {"_set": {"NSW": 0}}},
            {"dict": "KPOINTS", "action": {"_set": {"kpoints": [expected]}}},
        ]

    def test_quick_relax_then_relax(self) -> None:
        jobs = list(run_vasp.get_jobs(make_args(["quickrelax", "relax"])))
        quick, relax = jobs
        # lattice lengths ~(2.82, 4.88, 4.96) A -> int(18 / length) -> 6x3x3 gamma grid
        assert quick.settings_override == [
            {"dict": "INCAR", "action": {"_set": {"ISMEAR": 0}}},
            {"dict": "KPOINTS", "action": {"_set": Kpoints.gamma_automatic([6, 3, 3]).as_dict()}},
            {"dict": "INCAR", "action": {"_unset": {"ENCUT": 1}}},
        ]
        # the original ISMEAR, KPOINTS and ENCUT are restored for the following job
        assert relax.settings_override == [
            {"dict": "INCAR", "action": {"_set": {"ISMEAR": -5}}},
            {"dict": "KPOINTS", "action": {"_set": Kpoints.from_file("KPOINTS").as_dict()}},
            {"dict": "INCAR", "action": {"_set": {"ENCUT": 520.0}}},
            CONTCAR_COPY,
        ]

    def test_quick_relax_without_ismear_or_encut(self, vasp_dir) -> None:
        incar = Incar.from_file(vasp_dir / "INCAR")
        del incar["ISMEAR"], incar["ENCUT"]
        incar.write_file(vasp_dir / "INCAR")
        quick, relax = run_vasp.get_jobs(make_args(["quick_relax", "relax"]))
        assert all("ENCUT" not in str(s) for s in quick.settings_override)
        assert relax.settings_override[0] == {"dict": "INCAR", "action": {"_unset": {"ISMEAR": 1}}}
        assert all("ENCUT" not in str(s) for s in relax.settings_override)

    def test_ramp_u(self) -> None:
        jobs = list(run_vasp.get_jobs(make_args(["rampU", "rampU", "rampU"])))
        assert all(j.copy_magmom for j in jobs)
        ldauu = [j.settings_override[-1]["action"]["_set"]["LDAUU"] for j in jobs]
        ldauj = [j.settings_override[-1]["action"]["_set"]["LDAUJ"] for j in jobs]
        assert ldauu == [[0, 0, 0, 0], [0, 2, 3, 0], [0, 4, 6, 0]]
        assert ldauj == [[0, 0, 0, 0]] * 3

    @pytest.mark.xfail(
        strict=True,
        raises=ZeroDivisionError,
        reason="run_vasp.get_jobs divides by (n_ramp_u - 1), so a single rampU job raises ZeroDivisionError",
    )
    def test_single_ramp_u(self) -> None:
        (job,) = run_vasp.get_jobs(make_args(["rampU"]))
        assert job.copy_magmom

    def test_full_relax_delegates_to_full_opt_run(self, monkeypatch) -> None:
        calls = []

        def fake_full_opt_run(vasp_cmd):
            calls.append(vasp_cmd)
            yield from ("opt1", "opt2")

        monkeypatch.setattr(VaspJob, "full_opt_run", fake_full_opt_run)
        jobs = list(run_vasp.get_jobs(make_args(["full_relax"])))
        assert jobs == ["opt1", "opt2"]
        assert calls == [["mpirun", "-np", "4", "vasp"]]

    def test_unsupported_job(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            list(run_vasp.get_jobs(make_args(["relax", "bogus"])))
        assert exc.value.code == -1
        assert "Unsupported job type: bogus" in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("job", "expected_kwargs"),
        [
            ("nonscf_derived", {"copy_chgcar": False, "user_incar_settings": {"LWAVE": True}}),
            ("optics_derived", {"optics": True, "copy_chgcar": False, "nedos": 2001, "mode": "uniform"}),
        ],
    )
    def test_nonscf_derived(self, monkeypatch, job, expected_kwargs) -> None:
        calls = []
        vis = SimpleNamespace(incar=Incar({"ICHARG": 11}), kpoints=Kpoints.gamma_automatic([4, 4, 4]))

        def fake_from_prev_calc(prev_dir, **kwargs):
            calls.append((prev_dir, kwargs))
            return vis

        monkeypatch.setattr(vasp_sets.MPNonSCFSet, "from_prev_calc", fake_from_prev_calc)
        _, derived = run_vasp.get_jobs(make_args(["relax", job]))
        ((prev_dir, kwargs),) = calls
        assert prev_dir == "."
        assert expected_kwargs.items() <= kwargs.items()
        assert derived.settings_override == [
            CONTCAR_COPY,
            {"dict": "INCAR", "action": {"_set": {"ICHARG": 11}}},
            {"dict": "KPOINTS", "action": {"_set": vis.kpoints.as_dict()}},
        ]

    @pytest.fixture
    def static_vis(self, monkeypatch) -> SimpleNamespace:
        vis = SimpleNamespace(incar=Incar({"NSW": 0, "LWAVE": True}), kpoints=Kpoints.gamma_automatic([5, 5, 5]))
        monkeypatch.setattr(vasp_sets.MPStaticSet, "from_prev_calc", lambda *args, **kwargs: vis)
        return vis

    def test_static_derived(self, static_vis) -> None:
        _, derived = run_vasp.get_jobs(make_args(["relax", "static_derived"]))
        assert derived.settings_override[:3] == [
            CONTCAR_COPY,
            {"dict": "INCAR", "action": {"_set": {"NSW": 0, "LWAVE": True}}},
            {"dict": "KPOINTS", "action": {"_set": static_vis.kpoints.as_dict()}},
        ]

    @pytest.mark.xfail(
        strict=True,
        reason="static_derived also matches the later `elif job_type.startswith('static')` branch, which "
        "re-sets KPOINTS to the original grid and overrides the MPStaticSet-derived KPOINTS",
    )
    def test_static_derived_kpoints_not_overridden(self, static_vis) -> None:
        _, derived = run_vasp.get_jobs(make_args(["relax", "static_derived"]))
        assert kpoints_actions(derived.settings_override) == [
            {"dict": "KPOINTS", "action": {"_set": static_vis.kpoints.as_dict()}}
        ]

    @pytest.mark.xfail(
        strict=True,
        raises=ImportError,
        reason="MPStaticDielectricDFPTVaspInputSet no longer exists in pymatgen.io.vasp.sets",
    )
    def test_static_dielectric_derived(self) -> None:
        _, derived = run_vasp.get_jobs(make_args(["relax", "static_dielectric_derived"]))
        assert not derived.auto_npar


class TestDoRun:
    def test_builds_custodian(self, vasp_dir, monkeypatch) -> None:
        mock_custodian = MagicMock()
        monkeypatch.setattr(run_vasp, "Custodian", mock_custodian)
        args = make_args(
            ["relax", "relax"],
            handlers=[*DEFAULT_HANDLERS, "VaspErrorHandler?output_filename=my.out"],
            validators=["VasprunXMLValidator"],
            max_errors=7,
            scratch="/scratch",
            gzip=True,
        )
        run_vasp.do_run(args)

        mock_custodian.assert_called_once()
        (handlers, jobs, validators), kwargs = mock_custodian.call_args
        assert [type(h) for h in handlers] == [
            VaspErrorHandler,
            MeshSymmetryErrorHandler,
            UnconvergedErrorHandler,
            NonConvergingErrorHandler,
            PotimErrorHandler,
            VaspErrorHandler,
        ]
        assert handlers[-1].output_filename == "my.out"
        assert [type(v) for v in validators] == [VasprunXMLValidator]
        assert [j.suffix for j in jobs] == [".relax1", ".relax2"]
        assert kwargs == {"max_errors": 7, "scratch_dir": "/scratch", "gzipped_output": True, "checkpoint": True}
        mock_custodian.return_value.run.assert_called_once_with()


class TestMain:
    @pytest.fixture
    def parsed(self, monkeypatch) -> list[Namespace]:
        captured: list[Namespace] = []
        monkeypatch.setattr(run_vasp, "do_run", captured.append)
        return captured

    def test_defaults(self, monkeypatch, parsed) -> None:
        monkeypatch.setattr(sys, "argv", ["run_vasp", "relax"])
        run_vasp.main()
        (args,) = parsed
        assert args.command == "pvasp"
        assert args.jobs == ["relax"]
        assert args.handlers == DEFAULT_HANDLERS
        assert args.validators == ["VasprunXMLValidator"]
        assert args.static_kpoint == 1
        assert args.max_errors == 10
        assert args.scratch is None
        assert not args.gzip
        assert not args.no_auto_npar

    def test_options(self, monkeypatch, parsed) -> None:
        argv = ["run_vasp", "-c", "mpirun vasp", "-z", "-s", "/tmp/x", "-ks", "2", "-me", "3", "--no_auto_npar"]
        argv += ["-hd", "VaspErrorHandler", "-vd", "VasprunXMLValidator", "--", "relax", "static"]
        monkeypatch.setattr(sys, "argv", argv)
        run_vasp.main()
        (args,) = parsed
        assert args.command == "mpirun vasp"
        assert args.gzip
        assert args.scratch == "/tmp/x"
        assert args.static_kpoint == 2
        assert args.max_errors == 3
        assert args.no_auto_npar
        assert args.handlers == ["VaspErrorHandler"]
        assert args.jobs == ["relax", "static"]

    def test_requires_jobs(self, monkeypatch, parsed) -> None:
        monkeypatch.setattr(sys, "argv", ["run_vasp"])
        with pytest.raises(SystemExit):
            run_vasp.main()
        assert parsed == []
