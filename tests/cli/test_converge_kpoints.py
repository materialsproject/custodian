from __future__ import annotations

import shutil
import sys
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pymatgen.io.vasp import Poscar

from custodian.vasp.handlers import UnconvergedErrorHandler, VaspErrorHandler
from custodian.vasp.interpreter import VaspModder
from tests.cli.conftest import import_cli
from tests.conftest import TEST_FILES

N_ATOMS = 2


@pytest.fixture
def converge_kpoints():
    return import_cli("converge_kpoints")


@pytest.fixture
def fake_vasprun(converge_kpoints, monkeypatch):
    """Replace Vasprun with a stub yielding successive energies per atom; returns the list of reads."""
    energies: list[float] = []
    reads: list[str] = []

    def factory(filename):
        reads.append(filename)
        e_per_atom = energies[len(reads) - 1]
        return SimpleNamespace(final_energy=e_per_atom * N_ATOMS, final_structure=[None] * N_ATOMS)

    monkeypatch.setattr(converge_kpoints, "Vasprun", factory)
    return SimpleNamespace(energies=energies, reads=reads)


def kpoints_set(job):
    return next(s["action"]["_set"]["kpoints"] for s in job.settings_override if s.get("dict") == "KPOINTS")


@pytest.mark.usefixtures("vasp_dir")
class TestGetRuns:
    def test_first_job(self, converge_kpoints) -> None:
        job = next(converge_kpoints.get_runs(["vasp"]))
        assert job.vasp_cmd == ("vasp",)
        assert job.backup
        assert not job.final
        assert job.settings_override is None
        assert job.suffix == ".kpoints.8x2x2"

    def test_linear_converges(self, converge_kpoints, fake_vasprun) -> None:
        fake_vasprun.energies.extend([-5.0, -5.0005])
        jobs = list(converge_kpoints.get_runs(["vasp"], target=1e-3))
        assert len(jobs) == 2
        assert fake_vasprun.reads == ["vasprun.xml", "vasprun.xml"]
        assert [j.suffix for j in jobs] == [".kpoints.8x2x2", ".kpoints.16x4x4"]
        assert [j.backup for j in jobs] == [True, False]
        assert kpoints_set(jobs[1]) == [[16, 4, 4]]
        assert jobs[1].settings_override[0] == {"dict": "INCAR", "action": {"_set": {"ISTART": 1}}}

    def test_tighter_target_needs_more_steps(self, converge_kpoints, fake_vasprun) -> None:
        fake_vasprun.energies.extend([-5.0, -5.0005, -5.00051])
        jobs = list(converge_kpoints.get_runs(["vasp"], target=1e-4))
        assert [j.suffix for j in jobs] == [".kpoints.8x2x2", ".kpoints.16x4x4", ".kpoints.24x6x6"]

    def test_stops_at_max_steps(self, converge_kpoints, fake_vasprun) -> None:
        fake_vasprun.energies.extend([-1.0, -2.0, -3.0, -4.0])
        jobs = list(converge_kpoints.get_runs(["vasp"], max_steps=3))
        assert len(jobs) == 3
        assert len(fake_vasprun.reads) == 2
        assert kpoints_set(jobs[-1]) == [[24, 6, 6]]

    def test_inc_mode_first_increment(self, converge_kpoints, fake_vasprun) -> None:
        fake_vasprun.energies.extend([-1.0, -2.0])
        jobs = list(converge_kpoints.get_runs(["vasp"], mode="inc", max_steps=2))
        assert kpoints_set(jobs[1]) == [[9, 3, 3]]

    @pytest.mark.xfail(
        strict=True,
        reason="inc mode computes kpt + 1 independent of step, so the grid never grows beyond the first "
        "increment (8x2x2 -> 9x3x3 -> 9x3x3), and step 0 is labelled 9x3x3 although it runs 8x2x2",
    )
    def test_inc_mode_keeps_incrementing(self, converge_kpoints, fake_vasprun) -> None:
        fake_vasprun.energies.extend([-1.0, -2.0, -3.0])
        jobs = list(converge_kpoints.get_runs(["vasp"], mode="inc", max_steps=3))
        assert jobs[0].suffix == ".kpoints.8x2x2"
        assert [kpoints_set(j) for j in jobs[1:]] == [[[9, 3, 3]], [[10, 4, 4]]]

    @pytest.mark.xfail(
        strict=True,
        raises=ValueError,
        reason="the CONTCAR copy action uses the key 'filename' instead of 'file', which VaspModder rejects",
    )
    def test_settings_are_valid_modder_actions(self, converge_kpoints, fake_vasprun, vasp_dir) -> None:
        shutil.copy(f"{TEST_FILES}/CONTCAR", vasp_dir / "CONTCAR")
        fake_vasprun.energies.extend([-1.0, -2.0])
        _, second = converge_kpoints.get_runs(["vasp"], max_steps=2)
        VaspModder(directory=str(vasp_dir)).apply_actions(second.settings_override)
        assert Poscar.from_file(vasp_dir / "POSCAR").structure == Poscar.from_file(vasp_dir / "CONTCAR").structure


def test_do_run(converge_kpoints, vasp_dir, monkeypatch) -> None:
    mock_custodian = MagicMock()
    monkeypatch.setattr(converge_kpoints, "Custodian", mock_custodian)
    converge_kpoints.do_run(Namespace(command="mpirun vasp", target=1e-2, mode="linear", max_steps=4))

    (handlers, jobs), kwargs = mock_custodian.call_args
    assert [type(h) for h in handlers] == [VaspErrorHandler, UnconvergedErrorHandler]
    assert kwargs == {"max_errors": 10}
    assert next(jobs).vasp_cmd == ("mpirun", "vasp")
    mock_custodian.return_value.run.assert_called_once_with()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], {"command": "pvasp", "mode": "linear", "max_steps": 10, "target": 1e-3}),
        (
            ["-c", "mpirun vasp", "-i", "inc", "-m", "5", "-t", "0.01"],
            {"command": "mpirun vasp", "mode": "inc", "max_steps": 5, "target": 0.01},
        ),
    ],
)
def test_main(converge_kpoints, monkeypatch, argv, expected) -> None:
    parsed: list[Namespace] = []
    monkeypatch.setattr(converge_kpoints, "do_run", parsed.append)
    monkeypatch.setattr(sys, "argv", ["converge_kpoints", *argv])
    converge_kpoints.main()
    (args,) = parsed
    assert vars(args) == expected


def test_main_rejects_bad_mode(converge_kpoints, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["converge_kpoints", "-i", "quadratic"])
    with pytest.raises(SystemExit):
        converge_kpoints.main()
