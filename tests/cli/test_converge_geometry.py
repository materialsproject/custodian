from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custodian.vasp.handlers import (
    MeshSymmetryErrorHandler,
    NonConvergingErrorHandler,
    PotimErrorHandler,
    UnconvergedErrorHandler,
    VaspErrorHandler,
)
from tests.cli.conftest import import_cli

CONTCAR_COPY = {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
CG_START = [{"dict": "INCAR", "action": {"_set": {"IBRION": 2}}}]
CG_RESTART = [{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}}, CONTCAR_COPY]
RMM_DIIS = [{"dict": "INCAR", "action": {"_set": {"ISTART": 1, "IBRION": 1}}}, CONTCAR_COPY]


@pytest.fixture
def converge_geometry():
    return import_cli("converge_geometry")


@pytest.fixture
def ionic_steps(converge_geometry, monkeypatch) -> list[int]:
    """Number of ionic steps reported by each successive (stubbed) Vasprun read."""
    n_steps: list[int] = []
    reads = iter(n_steps)
    monkeypatch.setattr(
        converge_geometry, "Vasprun", lambda filename: SimpleNamespace(ionic_steps=[None] * next(reads))
    )
    return n_steps


def make_args(max_relax=10, **kwargs) -> Namespace:
    return Namespace(command="mpirun vasp", max_relax=max_relax, **kwargs)


class TestGetRuns:
    def test_cg_then_rmm_diis_until_single_ionic_step(self, converge_geometry, ionic_steps) -> None:
        ionic_steps.extend([5, 3, 1])
        jobs = list(converge_geometry.get_runs(make_args()))
        assert [j.suffix for j in jobs] == [".relax1", ".relax2", ".relax3", ".relax4"]
        assert [j.final for j in jobs] == [False, False, False, True]
        assert [j.backup for j in jobs] == [True, False, False, False]
        assert [j.settings_override for j in jobs] == [CG_START, CG_RESTART, RMM_DIIS, RMM_DIIS]
        assert jobs[0].vasp_cmd == ("mpirun", "vasp")

    def test_converged_after_first_run(self, converge_geometry, ionic_steps) -> None:
        ionic_steps.append(1)
        jobs = list(converge_geometry.get_runs(make_args()))
        assert len(jobs) == 2
        assert jobs[1].final
        assert jobs[1].settings_override == RMM_DIIS

    @pytest.mark.parametrize("max_relax", [1, 3])
    def test_stops_at_max_relax(self, converge_geometry, ionic_steps, max_relax) -> None:
        ionic_steps.extend([10] * 10)
        jobs = list(converge_geometry.get_runs(make_args(max_relax=max_relax)))
        assert len(jobs) == max_relax
        assert not any(j.final for j in jobs)


@pytest.mark.parametrize("gzip", [True, False])
def test_do_run(converge_geometry, monkeypatch, gzip) -> None:
    mock_custodian = MagicMock()
    monkeypatch.setattr(converge_geometry, "Custodian", mock_custodian)
    converge_geometry.do_run(make_args(gzip=gzip))

    (handlers, jobs), kwargs = mock_custodian.call_args
    assert [type(h) for h in handlers] == [
        VaspErrorHandler,
        MeshSymmetryErrorHandler,
        UnconvergedErrorHandler,
        NonConvergingErrorHandler,
        PotimErrorHandler,
    ]
    assert kwargs == {"max_errors": 10, "gzipped_output": gzip}
    assert next(jobs).suffix == ".relax1"
    mock_custodian.return_value.run.assert_called_once_with()


@pytest.mark.xfail(
    strict=True,
    reason="pyproject.toml registers the converge_geometry console script as custodian.cli.converge_geometry:main, "
    "but the module only has an `if __name__ == '__main__'` block and no main()",
)
def test_has_main_entry_point(converge_geometry) -> None:
    assert callable(getattr(converge_geometry, "main", None))
