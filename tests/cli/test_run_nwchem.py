from __future__ import annotations

import sys
from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from custodian.nwchem.handlers import NwchemErrorHandler
from custodian.nwchem.jobs import NwchemJob
from tests.cli.conftest import import_cli

run_nwchem = import_cli("run_nwchem")


@pytest.fixture
def mock_custodian(monkeypatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(run_nwchem, "Custodian", mock)
    return mock


def test_do_run(mock_custodian) -> None:
    args = Namespace(command="mpirun nwchem", infile="a.nw", outfile="a.nwout", scratch="/scratch", gzip=True)
    run_nwchem.do_run(args)

    ((handler,), (job,)), kwargs = mock_custodian.call_args
    assert isinstance(handler, NwchemErrorHandler)
    assert handler.output_filename == "a.nwout"
    assert isinstance(job, NwchemJob)
    assert job.nwchem_cmd == ["mpirun", "nwchem"]
    assert job.input_file == "a.nw"
    assert job.output_file == "a.nwout"
    assert kwargs == {"max_errors": 5, "scratch_dir": "/scratch", "gzipped_output": True, "checkpoint": True}
    mock_custodian.return_value.run.assert_called_once_with()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], {"command": "nwchem", "scratch": None, "infile": "mol.nw", "outfile": "mol.nwout", "gzip": False}),
        (
            ["-c", "mpirun nwchem", "-s", "/s", "-i", "x.nw", "-o", "x.out", "-z"],
            {"command": "mpirun nwchem", "scratch": "/s", "infile": "x.nw", "outfile": "x.out", "gzip": True},
        ),
    ],
)
def test_main_parses_args(monkeypatch, argv, expected) -> None:
    parsed: list[Namespace] = []
    monkeypatch.setattr(run_nwchem, "do_run", parsed.append)
    monkeypatch.setattr(sys, "argv", ["run_nwchem", *argv])
    run_nwchem.main()
    (args,) = parsed
    assert vars(args) == expected


def test_main_gzip_flag_reaches_custodian(monkeypatch, mock_custodian) -> None:
    monkeypatch.setattr(sys, "argv", ["run_nwchem", "-z"])
    run_nwchem.main()
    assert mock_custodian.call_args.kwargs["gzipped_output"] is True
