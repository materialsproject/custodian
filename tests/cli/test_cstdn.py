from __future__ import annotations

import json
import sys
from argparse import Namespace

import pytest
from ruamel.yaml import YAML

from custodian.custodian import Custodian
from custodian.vasp.handlers import AliasingErrorHandler, MeshSymmetryErrorHandler, VaspErrorHandler
from custodian.vasp.jobs import VaspJob
from custodian.vasp.validators import VasprunXMLValidator
from tests.cli.conftest import import_cli

cstdn = import_cli("cstdn")


@pytest.fixture
def ran(monkeypatch) -> list[Custodian]:
    """Stub Custodian.run so no job executes; returns the list of Custodian instances that were run."""
    instances: list[Custodian] = []

    def fake_run(self) -> None:
        instances.append(self)

    monkeypatch.setattr(Custodian, "run", fake_run)
    return instances


@pytest.fixture
def example_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PBS_NODEFILE", "/var/nodes")
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(cstdn.example_yaml)
    return spec_file


def test_example_yaml_is_valid() -> None:
    spec = YAML(typ="safe").load(cstdn.example_yaml)
    assert set(spec) == {"jobs", "jobs_common_params", "handlers", "validators", "custodian_params"}
    assert [j["params"]["suffix"] for j in spec["jobs"]] == [".relax1", ".relax2", ".static3"]


def test_run_example_spec(example_spec, ran) -> None:
    cstdn.run(Namespace(spec_file=[str(example_spec)]))

    (custodian,) = ran
    assert all(isinstance(j, VaspJob) for j in custodian.jobs)
    assert [j.suffix for j in custodian.jobs] == [".relax1", ".relax2", ".static3"]
    assert [j.final for j in custodian.jobs] == [False, False, True]
    # $-prefixed common params have environment variables expanded
    expected_cmd = ("mpirun", "-machinefile", "/var/nodes", "-np", "24", "vasp")
    assert all(j.vasp_cmd == expected_cmd for j in custodian.jobs)
    assert custodian.jobs[2].settings_override[-1] == {"dict": "INCAR", "action": {"_set": {"NSW": 0}}}
    assert [type(h) for h in custodian.handlers] == [VaspErrorHandler, AliasingErrorHandler, MeshSymmetryErrorHandler]
    assert [type(v) for v in custodian.validators] == [VasprunXMLValidator]
    assert custodian.max_errors == 10
    assert custodian.scratch_dir == "/tmp"
    assert custodian.gzipped_output
    assert custodian.checkpoint


def test_run_json_spec(tmp_path, monkeypatch, ran) -> None:
    monkeypatch.chdir(tmp_path)
    spec = {
        "jobs": [{"jb": "custodian.vasp.jobs.VaspJob", "params": {"vasp_cmd": ["vasp"], "final": True}}],
        "custodian_params": {"max_errors": 3},
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    cstdn.run(Namespace(spec_file=["spec.json"]))

    (custodian,) = ran
    (job,) = custodian.jobs
    assert job.vasp_cmd == ("vasp",)
    assert custodian.handlers == []
    assert custodian.validators == []
    assert custodian.max_errors == 3


def test_main_run(example_spec, monkeypatch, ran) -> None:
    monkeypatch.setattr(sys, "argv", ["cstdn", "run", str(example_spec)])
    cstdn.main()
    assert len(ran) == 1
    assert len(ran[0].jobs) == 3


def test_main_example(monkeypatch, capsys, ran) -> None:
    monkeypatch.setattr(sys, "argv", ["cstdn", "example"])
    cstdn.main()
    assert capsys.readouterr().out.strip() == cstdn.example_yaml.strip()
    assert ran == []


def test_main_without_subcommand_prints_help(monkeypatch, capsys, ran) -> None:
    monkeypatch.setattr(sys, "argv", ["cstdn"])
    with pytest.raises(SystemExit) as exc:
        cstdn.main()
    assert exc.value.code == 0
    assert "usage: cstdn" in capsys.readouterr().out
    assert ran == []
