import contextlib
import getpass
import importlib.util
import io
import json
import logging
import os
import random
import socket
import subprocess
import sys
import tarfile
import types
import unittest
from glob import glob

import pytest
from monty.serialization import loadfn
from ruamel.yaml import YAML


@pytest.fixture(autouse=True)
def _seed_rng() -> None:
    """Seed RNG for deterministic ExampleJob.run() behavior across all tests.
    Needed for ExampleJob.run() with random.uniform(0, 1) to not be flaky."""
    random.seed(42)


from custodian.custodian import (  # noqa: E402
    Custodian,
    ErrorHandler,
    Job,
    MaxCorrectionsError,
    MaxCorrectionsPerHandlerError,
    MaxCorrectionsPerJobError,
    NonRecoverableError,
    ReturnCodeError,
    ValidationError,
    Validator,
)


class ExitCodeJob(Job):
    def __init__(self, exitcode=0) -> None:
        self.exitcode = exitcode

    def setup(self, directory="./") -> None:
        pass

    def run(self, directory="./"):
        return subprocess.Popen(f"exit {self.exitcode}", cwd=directory, shell=True)

    def postprocess(self, directory="./") -> None:
        pass


class ExampleJob(Job):
    def __init__(self, jobid, params=None) -> None:
        if params is None:
            params = {"initial": 0, "total": 0}
        self.jobid = jobid
        self.params = params

    def setup(self, directory="./") -> None:
        self.params["initial"] = 0
        self.params["total"] = 0

    def run(self, directory="./") -> None:
        sequence = [random.uniform(0, 1) for _ in range(100)]
        self.params["total"] = self.params["initial"] + sum(sequence)

    def postprocess(self, directory="./") -> None:
        pass

    @property
    def name(self) -> str:
        return f"ExampleJob{self.jobid}"


class ExampleHandler(ErrorHandler):
    def __init__(self, params) -> None:
        self.params = params

    def check(self, directory="./"):
        return self.params["total"] < 50

    def correct(self, directory="./"):
        self.params["initial"] += 1
        return {"errors": "total < 50", "actions": "increment by 1"}


class ExampleHandler1b(ExampleHandler):
    """
    This handler always can apply a correction, but will only apply it twice before raising.
    """

    max_num_corrections = 2
    raise_on_max = True


class ExampleHandler1c(ExampleHandler):
    """
    This handler always can apply a correction, but will only apply it twice and then not anymore.
    """

    max_num_corrections = 2
    raise_on_max = False


class ExampleHandler2(ErrorHandler):
    """
    This handler always result in an error.
    """

    def __init__(self, params) -> None:
        self.params = params
        self.has_error = False

    def check(self, directory="./") -> bool:
        return True

    def correct(self, directory="./"):
        self.has_error = True
        return {"errors": "Unrecoverable error", "actions": None}


class ExampleHandler2b(ExampleHandler2):
    """
    This handler always result in an error. No runtime error though
    """

    raises_runtime_error = False

    def correct(self, directory="./"):
        self.has_error = True
        return {"errors": "Unrecoverable error", "actions": []}


class ExampleValidator1(Validator):
    def __init__(self) -> None:
        pass

    def check(self, directory="./") -> bool:
        return False


class ExampleValidator2(Validator):
    def __init__(self) -> None:
        pass

    def check(self, directory="./") -> bool:
        return True


class CustodianTest(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _run_in_tmp_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)

    def test_exitcode_error(self) -> None:
        c = Custodian([], [ExitCodeJob(0)])
        c.run()
        c = Custodian([], [ExitCodeJob(1)])
        with pytest.raises(
            ReturnCodeError,
        ):
            c.run()
        assert c.run_log[-1]["nonzero_return_code"]
        c = Custodian([], [ExitCodeJob(1)], terminate_on_nonzero_returncode=False)
        c.run()

    def test_run(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(n_jobs)],
            max_errors=n_jobs,
        )
        output = c.run()
        assert len(output) == n_jobs
        ExampleHandler(params).as_dict()

    def test_run_interrupted(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(n_jobs)],
            max_errors=n_jobs,
        )

        assert c.run_interrupted() == n_jobs
        assert c.run_interrupted() == n_jobs

        total_done = 1
        while total_done < n_jobs:
            c.jobs[n_jobs - 1].run()
            if params["total"] > 50:
                assert c.run_interrupted() == n_jobs - total_done
                total_done += 1

    def test_unrecoverable(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        handler = ExampleHandler2(params)
        c = Custodian([handler], [ExampleJob(i, params) for i in range(n_jobs)], max_errors=n_jobs)
        with pytest.raises(NonRecoverableError):
            c.run()
        assert handler.has_error
        handler = ExampleHandler2b(params)
        c = Custodian([handler], [ExampleJob(i, params) for i in range(n_jobs)], max_errors=n_jobs)
        c.run()
        assert handler.has_error
        assert c.run_log[-1]["handler"] == handler

    def test_max_errors(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        handler = ExampleHandler(params)
        c = Custodian(
            [handler],
            [ExampleJob(i, params) for i in range(n_jobs)],
            max_errors=1,
            max_errors_per_job=10,
        )
        with pytest.raises(MaxCorrectionsError):
            c.run()
        assert c.run_log[-1]["max_errors"]

    def test_max_errors_per_job(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        handler = ExampleHandler(params)
        c = Custodian(
            [handler],
            [ExampleJob(i, params) for i in range(n_jobs)],
            max_errors=n_jobs,
            max_errors_per_job=1,
        )
        with pytest.raises(MaxCorrectionsPerJobError):
            c.run()
        assert c.run_log[-1]["max_errors_per_job"]

    def test_max_errors_per_handler_raise(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        handler = ExampleHandler1b(params)
        c = Custodian(
            [handler],
            [ExampleJob(i, params) for i in range(n_jobs)],
            max_errors=n_jobs * 10,
            max_errors_per_job=1000,
        )
        with pytest.raises(MaxCorrectionsPerHandlerError):
            c.run()
        assert handler.n_applied_corrections == 2
        assert len(c.run_log[-1]["corrections"]) == 2
        assert c.run_log[-1]["max_errors_per_handler"]
        assert c.run_log[-1]["handler"] == handler

    def test_max_errors_per_handler_warning(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler1c(params)],
            [ExampleJob(i, params) for i in range(n_jobs)],
            max_errors=n_jobs * 10,
            max_errors_per_job=1000,
        )
        c.run()
        assert all(len(r["corrections"]) <= 2 for r in c.run_log)

    def test_validators(self) -> None:
        n_jobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(n_jobs)],
            [ExampleValidator1()],
            max_errors=n_jobs,
        )
        output = c.run()
        assert len(output) == n_jobs

        n_jobs = 100
        params = {"initial": 0, "total": 0}
        v = ExampleValidator2()
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(n_jobs)],
            [v],
            max_errors=n_jobs,
        )
        with pytest.raises(ValidationError):
            c.run()
        assert c.run_log[-1]["validator"] == v

    def test_from_spec(self) -> None:
        spec = """jobs:
- jb: custodian.vasp.jobs.VaspJob
  params:
    final: False
    suffix: .relax1
- jb: custodian.vasp.jobs.VaspJob
  params:
    final: True
    suffix: .relax2
    settings_override: {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
jobs_common_params:
  $vasp_cmd: ["mpirun", "-machinefile", "$PBS_NODEFILE", "-np", "24", "/opt/vasp/5.4.1/bin/vasp"]
handlers:
- hdlr: custodian.vasp.handlers.VaspErrorHandler
- hdlr: custodian.vasp.handlers.AliasingErrorHandler
- hdlr: custodian.vasp.handlers.MeshSymmetryErrorHandler
validators:
- vldr: custodian.vasp.validators.VasprunXMLValidator
custodian_params:
  $scratch_dir: $TMPDIR"""

        os.environ["TMPDIR"] = "/tmp/random"
        os.environ["PBS_NODEFILE"] = "whatever"
        dct = YAML(typ="rt").load(spec)
        c = Custodian.from_spec(dct)
        assert c.jobs[0].vasp_cmd[2] == "whatever"
        assert c.scratch_dir == "/tmp/random"
        assert len(c.jobs) == 2
        assert len(c.handlers) == 3
        assert len(c.validators) == 1


# ---------------------------------------------------------------------------
# pytest-style tests below. These run in an isolated tmp_path working directory.
# ---------------------------------------------------------------------------

RUN_CALLS: list[int] = []


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Run each test in an isolated temporary working directory."""
    monkeypatch.chdir(tmp_path)
    RUN_CALLS.clear()
    return tmp_path


class RecordingJob(Job):
    """Job that records its execution in RUN_CALLS and optionally crashes."""

    def __init__(self, jobid, crash=False) -> None:
        self.jobid = jobid
        self.crash = crash

    def setup(self, directory="./") -> None:
        pass

    def run(self, directory="./") -> None:
        if self.crash:
            raise RuntimeError(f"simulated crash in job {self.jobid}")
        RUN_CALLS.append(self.jobid)
        with open(os.path.join(directory, f"job{self.jobid}.out"), "w") as file:
            file.write(str(self.jobid))

    def postprocess(self, directory="./") -> None:
        pass


class FlagFileHandler(ErrorHandler):
    """Detects an error if a flag file exists; correcting removes the flag."""

    def __init__(self, flag="error.flag") -> None:
        self.flag = flag

    def check(self, directory="./") -> bool:
        return os.path.isfile(os.path.join(directory, self.flag))

    def correct(self, directory="./"):
        os.remove(os.path.join(directory, self.flag))
        return {"errors": [self.flag], "actions": [{"file": self.flag, "action": "removed"}]}


class AlwaysCorrectHandler(ErrorHandler):
    """Always detects an error and always applies a (no-op) correction."""

    def __init__(self) -> None:
        pass

    def check(self, directory="./") -> bool:
        return True

    def correct(self, directory="./"):
        return {"errors": ["always"], "actions": [{"action": "noop"}]}


class BrokenCheckHandler(ErrorHandler):
    """Handler whose check() itself raises."""

    def __init__(self) -> None:
        pass

    def check(self, directory="./") -> bool:
        raise RuntimeError("broken check")

    def correct(self, directory="./"):
        return {"errors": [], "actions": []}


class BrokenCorrectHandler(ErrorHandler):
    """Handler that detects an error but whose correct() raises."""

    def __init__(self) -> None:
        pass

    def check(self, directory="./") -> bool:
        return True

    def correct(self, directory="./"):
        raise RuntimeError("broken correct")


class SoftFailHandler(ErrorHandler):
    """Handler whose check() raises a CustodianError with raises=False."""

    def __init__(self) -> None:
        pass

    def check(self, directory="./") -> bool:
        raise NonRecoverableError("soft failure", raises=False, handler=self)

    def correct(self, directory="./"):
        return {"errors": [], "actions": []}


def _jobid(entry):
    """Job id of a run-log entry; reloaded logs hold decoded Jobs, in-memory ones hold dicts."""
    job = entry["job"]
    return job.jobid if isinstance(job, Job) else job["jobid"]


def _make_tar(path, members) -> None:
    """Write a tar.gz with the given {name: bytes} regular-file members."""
    with tarfile.open(path, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


# ----------------------------- checkpointing --------------------------------


def test_checkpoint_round_trip(workdir) -> None:
    crashing = Custodian([], [RecordingJob(1), RecordingJob(2, crash=True), RecordingJob(3)], checkpoint=True)
    assert crashing.restart == 0
    assert crashing.run_log == []
    with pytest.raises(RuntimeError, match="simulated crash in job 2"):
        crashing.run()
    assert RUN_CALLS == [1]
    # Only the checkpoint after job 1 exists; the run log was flushed in `finally`.
    assert [os.path.basename(f) for f in glob(str(workdir / "custodian.chk.*.tar.gz"))] == ["custodian.chk.1.tar.gz"]
    assert len(loadfn(workdir / "custodian.json")) == 2

    # Simulate lost outputs, then restart from the checkpoint.
    os.remove(workdir / "job1.out")
    RUN_CALLS.clear()
    resumed = Custodian([], [RecordingJob(1), RecordingJob(2), RecordingJob(3)], checkpoint=True)
    assert resumed.restart == 1
    # Run log is restored from the checkpoint (job 1 only), not from the crashed run's log.
    assert len(resumed.run_log) == 1
    assert _jobid(resumed.run_log[0]) == 1
    # Checkpointed outputs were restored.
    assert (workdir / "job1.out").read_text() == "1"

    run_log = resumed.run()
    assert RUN_CALLS == [2, 3]
    assert [_jobid(entry) for entry in run_log] == [1, 2, 3]
    # Successful completion cleans up all checkpoints.
    assert glob(str(workdir / "custodian.chk.*.tar.gz")) == []


def test_load_checkpoint_picks_lowest_index(workdir) -> None:
    for idx in (10, 2, 5):
        log = json.dumps([{"job": {"jobid": i}, "corrections": []} for i in range(idx)]).encode()
        _make_tar(workdir / f"custodian.chk.{idx}.tar.gz", {"custodian.json": log, f"marker{idx}": b""})
    restart, run_log = Custodian._load_checkpoint(str(workdir))
    # Numeric (not lexicographic) ordering: 2 < 5 < 10.
    assert restart == 2
    assert len(run_log) == 2
    assert (workdir / "marker2").exists()
    assert not (workdir / "marker5").exists()
    assert not (workdir / "marker10").exists()


def test_load_checkpoint_no_checkpoint(workdir) -> None:
    assert Custodian._load_checkpoint(str(workdir)) == (0, [])


def test_save_checkpoint_replaces_old(workdir) -> None:
    (workdir / "a.txt").write_text("a")
    Custodian._save_checkpoint(str(workdir), 1)
    Custodian._save_checkpoint(str(workdir), 2)
    chk_pts = glob(str(workdir / "custodian.chk.*.tar.gz"))
    assert [os.path.basename(f) for f in chk_pts] == ["custodian.chk.2.tar.gz"]
    with tarfile.open(chk_pts[0]) as tar:
        names = tar.getnames()
    assert "./a.txt" in names
    # The archive must not contain itself.
    assert not any(name.endswith(".tar.gz") for name in names)
    Custodian._delete_checkpoints(str(workdir))
    assert glob(str(workdir / "custodian.chk.*.tar.gz")) == []


def test_save_checkpoint_failure_is_logged(workdir, monkeypatch, caplog) -> None:
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(sys.modules[Custodian.__module__].tarfile, "open", boom)
    with caplog.at_level(logging.INFO, logger=Custodian.__module__):
        Custodian._save_checkpoint(str(workdir), 1)  # must not raise
    assert "Checkpointing failed" in caplog.text
    assert "OSError: disk full" in caplog.text
    assert not (workdir / "custodian.chk.1.tar.gz").exists()


# --------------------------- safe_extract guard -----------------------------


@pytest.mark.parametrize("member_name", ["../evil.txt", "sub/../../evil.txt", "ABSOLUTE"])
def test_load_checkpoint_rejects_path_traversal(tmp_path, member_name) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    evil = tmp_path / "evil.txt"
    if member_name == "ABSOLUTE":
        member_name = str(evil)
    _make_tar(
        run_dir / "custodian.chk.1.tar.gz",
        {"custodian.json": b"[]", "benign.txt": b"ok", member_name: b"pwned"},
    )
    with pytest.raises(Exception, match="Attempted Path Traversal in Tar File"):
        Custodian._load_checkpoint(str(run_dir))
    # Nothing extracted anywhere: all members are validated before any is written.
    assert not evil.exists()
    assert sorted(os.listdir(run_dir)) == ["custodian.chk.1.tar.gz"]


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_load_checkpoint_rejects_link_traversal(tmp_path, link_type) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with tarfile.open(run_dir / "custodian.chk.1.tar.gz", mode="w:gz") as tar:
        link = tarfile.TarInfo("link")
        link.type = link_type
        link.linkname = str(outside)
        tar.addfile(link)
        for name, data in {"link/evil.txt": b"pwned", "custodian.json": b"[]"}.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    with pytest.raises(Exception, match="Attempted Path Traversal in Tar File"):
        Custodian._load_checkpoint(str(run_dir))
    assert not (outside / "evil.txt").exists(), "tar member was written outside the checkpoint directory"
    assert sorted(os.listdir(run_dir)) == ["custodian.chk.1.tar.gz"]


def test_load_checkpoint_keeps_internal_symlinks(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with tarfile.open(run_dir / "custodian.chk.1.tar.gz", mode="w:gz") as tar:
        for name, data in {"custodian.json": b"[]", "sub/CONTCAR": b"structure"}.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("POSCAR")
        link.type = tarfile.SYMTYPE
        link.linkname = "sub/CONTCAR"
        tar.addfile(link)
    assert Custodian._load_checkpoint(str(run_dir)) == (1, [])
    assert (run_dir / "POSCAR").is_symlink()
    assert (run_dir / "POSCAR").read_text() == "structure"


# ----------------------------- run_interrupted ------------------------------


def _interrupted(jobs, handlers=(), validators=(), **kwargs):
    """A fresh Custodian per call mimics separate process invocations."""
    kwargs.setdefault("max_errors", 10)
    return Custodian(list(handlers), jobs, list(validators), **kwargs)


def test_run_interrupted_correct_then_finish(workdir) -> None:
    jobs = [RecordingJob(0), RecordingJob(1)]
    handler = FlagFileHandler()

    assert _interrupted(jobs, [handler]).run_interrupted() == 2  # set up job 0

    (workdir / "error.flag").touch()  # job 0 "ran" and hit an error
    c = _interrupted(jobs, [handler])
    assert c.run_interrupted() == 2  # corrected; rerun job 0
    assert not (workdir / "error.flag").exists()
    assert len(c.run_log) == 1
    assert c.run_log[0]["corrections"][0]["errors"] == ["error.flag"]

    c = _interrupted(jobs, [handler])
    assert c.run_interrupted() == 1  # job 0 OK; job 1 set up
    # Run log was reloaded from disk: prior corrections preserved, new entry appended.
    assert [entry["job_n"] for entry in c.run_log] == [0, 1]
    assert len(c.run_log[0]["corrections"]) == 1
    assert not c.finished

    (workdir / "OUTCAR").write_text("output")
    c = _interrupted(jobs, [handler], gzipped_output=True)
    assert c.run_interrupted() == 0
    assert c.finished
    assert (workdir / "OUTCAR.gz").exists()
    assert not (workdir / "OUTCAR").exists()


def test_run_interrupted_unrecoverable(workdir) -> None:
    params = {"initial": 0, "total": 0}
    jobs = [ExampleJob(0, params)]
    handler = ExampleHandler2(params)
    assert _interrupted(jobs, [handler]).run_interrupted() == 1
    c = _interrupted(jobs, [handler])
    with pytest.raises(NonRecoverableError, match="Unrecoverable error for handler"):
        c.run_interrupted()
    assert c.run_log[-1]["handler"] is handler
    # The run log is flushed to disk even when raising.
    assert len(loadfn(workdir / "custodian.json")[-1]["corrections"]) == 1


def test_run_interrupted_validator_fails(workdir) -> None:
    jobs = [RecordingJob(0)]
    validator = ExampleValidator2()
    assert _interrupted(jobs, validators=[validator]).run_interrupted() == 1
    c = _interrupted(jobs, validators=[validator])
    with pytest.raises(ValidationError, match="Validation failed"):
        c.run_interrupted()
    assert c.run_log[-1]["validator"] is validator
    assert not c.finished


def test_run_interrupted_non_raising_custodian_error_is_swallowed(workdir) -> None:
    jobs = [RecordingJob(0)]
    assert _interrupted(jobs).run_interrupted() == 1
    assert _interrupted(jobs, [SoftFailHandler()]).run_interrupted() is None
    assert (workdir / "custodian.json").exists()


@pytest.mark.parametrize(
    ("kwargs", "exc", "flag"),
    [
        ({"max_errors": 2, "max_errors_per_job": 10}, MaxCorrectionsError, "max_errors"),
        ({"max_errors": 10, "max_errors_per_job": 2}, MaxCorrectionsPerJobError, "max_errors_per_job"),
    ],
)
def test_run_interrupted_enforces_max_errors(workdir, kwargs, exc, flag) -> None:
    jobs = [RecordingJob(0)]
    assert _interrupted(jobs, [AlwaysCorrectHandler()], **kwargs).run_interrupted() == 1  # set up
    # First correction stays under the limit; the second reaches it.
    assert _interrupted(jobs, [AlwaysCorrectHandler()], **kwargs).run_interrupted() == 1
    with pytest.raises(exc):
        _interrupted(jobs, [AlwaysCorrectHandler()], **kwargs).run_interrupted()
    run_log = loadfn(workdir / "custodian.json")
    assert run_log[-1][flag] is True
    assert len(run_log[-1]["corrections"]) == 2


def test_run_interrupted_max_errors_counts_across_jobs(workdir) -> None:
    jobs = [RecordingJob(0), RecordingJob(1)]
    handler = FlagFileHandler()
    assert _interrupted(jobs, [handler], max_errors=2).run_interrupted() == 2
    (workdir / "error.flag").touch()
    assert _interrupted(jobs, [handler], max_errors=2).run_interrupted() == 2  # 1 error in job 0
    assert _interrupted(jobs, [handler], max_errors=2).run_interrupted() == 1  # job 0 done, job 1 set up
    (workdir / "error.flag").touch()
    with pytest.raises(MaxCorrectionsError):  # 2nd error overall, 1st in job 1
        _interrupted(jobs, [handler], max_errors=2, max_errors_per_job=5).run_interrupted()


# --------------------------- _run_job / _do_check ---------------------------


@pytest.mark.parametrize("handler_cls", [BrokenCheckHandler, BrokenCorrectHandler])
def test_handler_exception_propagates_without_skip(workdir, handler_cls) -> None:
    c = Custodian([handler_cls()], [RecordingJob(0)], skip_over_errors=False)
    with pytest.raises(RuntimeError, match="broken"):
        c.run()
    # Run log is flushed in `finally` even on a non-Custodian exception.
    assert len(loadfn(workdir / "custodian.json")) == 1


@pytest.mark.parametrize("handler_cls", [BrokenCheckHandler, BrokenCorrectHandler])
def test_do_check_skip_over_errors_records_bad_handler(workdir, handler_cls) -> None:
    good = FlagFileHandler()
    (workdir / "error.flag").touch()
    c = Custodian([handler_cls(), good], [RecordingJob(0)], skip_over_errors=True, max_errors=10)
    c.run_log = [{"corrections": []}]
    assert c._do_check(c.handlers) is True
    corrections = c.run_log[-1]["corrections"]
    assert corrections[0]["errors"][0].startswith("Bad handler=")
    assert corrections[0]["actions"] == []
    assert corrections[0]["skipped"] is True
    assert isinstance(corrections[0]["handler"], handler_cls)
    # The subsequent handler still ran.
    assert corrections[1]["handler"] is good
    assert not (workdir / "error.flag").exists()
    # Only the real correction counts as an error.
    assert c.total_errors == c.errors_current_job == 1


@pytest.mark.parametrize("handler_cls", [BrokenCheckHandler, BrokenCorrectHandler])
def test_do_check_only_skipped_handlers_is_not_an_error(workdir, handler_cls) -> None:
    c = Custodian([handler_cls()], [RecordingJob(0)], skip_over_errors=True)
    c.run_log = [{"corrections": []}]
    assert c._do_check(c.handlers) is False
    assert c.total_errors == c.errors_current_job == 0
    assert c.run_log[-1]["corrections"][0]["skipped"] is True


@pytest.mark.parametrize("handler_cls", [BrokenCheckHandler, BrokenCorrectHandler])
def test_run_skip_over_errors_skips_bad_handler(workdir, handler_cls) -> None:
    job = RecordingJob(0)
    c = Custodian([handler_cls()], [job], skip_over_errors=True)
    run_log = c.run()
    # The job runs once and finishes; the failed handler is logged but neither reruns nor aborts it.
    assert len(run_log) == 1
    assert run_log[0]["corrections"][0]["errors"][0].startswith("Bad handler=")
    assert RUN_CALLS == [0]
    assert c.total_errors == 0


def test_run_interrupted_skip_over_errors_skips_bad_handler(workdir) -> None:
    jobs = [RecordingJob(0)]
    assert _interrupted(jobs).run_interrupted() == 1
    c = _interrupted(jobs, [BrokenCorrectHandler()], skip_over_errors=True)
    assert c.run_interrupted() == 0
    assert c.finished


class SleepJob(Job):
    """Popen job: the first run sleeps, subsequent runs exit immediately."""

    def __init__(self, first_sleep=30) -> None:
        self.first_sleep = first_sleep
        self.n_runs = 0
        self.n_terminations = 0
        self._proc: subprocess.Popen | None = None

    def setup(self, directory="./") -> None:
        pass

    def run(self, directory="./"):
        self.n_runs += 1
        duration = self.first_sleep if self.n_runs == 1 else 0
        self._proc = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({duration})"], cwd=directory)
        return self._proc

    def postprocess(self, directory="./") -> None:
        pass

    def terminate(self, directory="./") -> None:
        self.n_terminations += 1
        assert self._proc is not None
        self._proc.kill()
        # Reap immediately so the next poll() deterministically sees the exit.
        self._proc.wait()


class OneShotMonitor(ErrorHandler):
    """Monitor that reports an error only on its first check."""

    is_monitor = True

    def __init__(self, is_terminating=True) -> None:
        self.is_terminating = is_terminating
        self.n_checks = 0

    def check(self, directory="./") -> bool:
        self.n_checks += 1
        return self.n_checks == 1

    def correct(self, directory="./"):
        return {"errors": ["monitor"], "actions": [{"action": "noop"}]}


@pytest.mark.parametrize("n_monitors", [1, 2])
def test_run_with_terminating_monitors(workdir, n_monitors) -> None:
    job = SleepJob(first_sleep=30)
    monitors = [OneShotMonitor(is_terminating=True) for _ in range(n_monitors)]
    c = Custodian(monitors, [job], max_errors=10, polling_time_step=0.02, monitor_freq=2)
    assert c.monitors == monitors
    run_log = c.run()
    # Killed by the monitor, corrected, then rerun to completion.
    assert job.n_runs == 2
    # Several terminating monitors firing at once terminate the job only once.
    assert job.n_terminations == 1
    assert [corr["handler"] for corr in run_log[0]["corrections"]] == monitors
    assert c.total_errors == n_monitors


def test_run_with_non_terminating_monitor(workdir) -> None:
    """Current semantics: a non-terminating monitor's correction is recorded, but because each later
    monitor pass overwrites ``has_error``, a subsequent clean check means the job is not rerun
    (the WalltimeHandler-style "flag a graceful stop" use case)."""
    job = SleepJob(first_sleep=0.5)
    monitor = OneShotMonitor(is_terminating=False)
    c = Custodian([monitor], [job], max_errors=10, polling_time_step=0.02, monitor_freq=2)
    run_log = c.run()
    assert job.n_terminations == 0
    assert monitor.n_checks > 2  # monitored repeatedly while running, then once more after exit
    assert [corr["handler"] for corr in run_log[0]["corrections"]] == [monitor]
    assert c.total_errors == 1
    assert job.n_runs == 1


def test_terminate_func_called_after_wait(workdir) -> None:
    calls = []
    c = Custodian([], [ExitCodeJob(0)], terminate_func=lambda: calls.append(1), polling_time_step=0)
    c.run()
    assert calls == [1]


def test_nonzero_returncode_warns_when_not_terminating(workdir) -> None:
    c = Custodian([], [ExitCodeJob(3)], terminate_on_nonzero_returncode=False)
    with pytest.warns(UserWarning, match="non-zero return code"):
        c.run()
    assert not c.run_log[-1]["nonzero_return_code"]


def test_nonzero_returncode_raises(workdir) -> None:
    c = Custodian([], [ExitCodeJob(3)])
    with pytest.raises(ReturnCodeError, match="Job return code is 3"):
        c.run()
    assert c.run_log[-1]["nonzero_return_code"]


def test_run_with_scratch_dir_and_gzip(workdir, monkeypatch) -> None:
    scratch = workdir / "scratch"
    scratch.mkdir()
    rundir = workdir / "rundir"
    rundir.mkdir()
    monkeypatch.chdir(rundir)
    c = Custodian([], [RecordingJob(7)], scratch_dir=str(scratch), gzipped_output=True)
    c.run()
    assert c.directory == str(rundir)
    # Outputs produced in scratch are copied back and gzipped.
    assert (rundir / "job7.out.gz").exists()
    assert (rundir / "custodian.json.gz").exists()


# ------------------------------ Sentry opt-in -------------------------------


@pytest.fixture
def sentry_stub(monkeypatch):
    """Stub sentry_sdk in sys.modules, recording init and scope calls."""
    stub = types.SimpleNamespace(dsn=None, scope=types.SimpleNamespace(user=None, tags={}))
    stub.scope.set_tag = stub.scope.tags.__setitem__

    def init(dsn=None) -> None:
        stub.dsn = dsn

    @contextlib.contextmanager
    def configure_scope():
        yield stub.scope

    stub.init = init
    stub.configure_scope = configure_scope
    monkeypatch.setitem(sys.modules, "sentry_sdk", stub)
    return stub


def _exec_custodian_module():
    """Execute custodian.py as a fresh module, leaving sys.modules['custodian.custodian'] untouched.

    importlib.reload would replace the exception classes imported by this test module.
    """
    path = sys.modules[Custodian.__module__].__file__
    spec = importlib.util.spec_from_file_location("custodian._sentry_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("opt_in", ["true", "True", "TRUE"])
def test_sentry_opt_in(monkeypatch, sentry_stub, opt_in) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.setenv("CUSTODIAN_REPORTING_OPT_IN", opt_in)
    monkeypatch.setattr(getpass, "getuser", lambda: "tester")
    module = _exec_custodian_module()
    assert module.SENTRY_DSN.startswith("https://")
    assert module.SENTRY_DSN.endswith("@sentry.io/1470881")
    assert sentry_stub.dsn == module.SENTRY_DSN
    assert sentry_stub.scope.user == {"username": "tester"}
    assert sentry_stub.scope.tags == {"hostname": socket.gethostname()}


def test_sentry_custom_dsn_and_getuser_failure(monkeypatch, sentry_stub) -> None:
    def no_user():
        raise OSError("no user")

    monkeypatch.setenv("SENTRY_DSN", "https://custom@example.invalid/1")
    monkeypatch.setenv("CUSTODIAN_REPORTING_OPT_IN", "False")
    monkeypatch.setattr(getpass, "getuser", no_user)
    _exec_custodian_module()
    assert sentry_stub.dsn == "https://custom@example.invalid/1"
    assert sentry_stub.scope.user is None  # getuser failure is tolerated
    assert "hostname" in sentry_stub.scope.tags


def test_sentry_disabled_by_default(monkeypatch, sentry_stub) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("CUSTODIAN_REPORTING_OPT_IN", raising=False)
    module = _exec_custodian_module()
    assert module.SENTRY_DSN is None
    assert sentry_stub.dsn is None


# ------------------------------- from_spec ----------------------------------


class ParamJob(Job):
    """Job that just stores the parameters it was constructed with."""

    def __init__(self, env=None, cmd=None, payload=None) -> None:
        self.env = env
        self.cmd = cmd
        self.payload = payload

    def setup(self, directory="./") -> None:
        pass

    def run(self, directory="./") -> None:
        pass

    def postprocess(self, directory="./") -> None:
        pass


def test_from_spec_expands_env_vars_and_decodes_params(monkeypatch) -> None:
    monkeypatch.setenv("CUSTODIAN_TEST_FOO", "foo-value")
    monkeypatch.setenv("CUSTODIAN_TEST_SCRATCH", "/scratch/here")
    mod = __name__
    spec = {
        "jobs": [
            # "$"-prefixed dict params have each value env-expanded.
            {"jb": f"{mod}.ParamJob", "params": {"$env": {"A": "$CUSTODIAN_TEST_FOO", "B": "plain"}}},
            # Non-"$" params are passed through verbatim, but MSON dicts are decoded.
            {
                "jb": f"{mod}.ParamJob",
                "params": {"env": {"A": "$CUSTODIAN_TEST_FOO"}, "payload": ExampleValidator1().as_dict()},
            },
        ],
        "jobs_common_params": {"$cmd": ["run", "$CUSTODIAN_TEST_FOO"]},
        "handlers": [{"hdlr": f"{mod}.FlagFileHandler", "params": {"flag": "stop.flag"}}],
        "validators": [{"vldr": f"{mod}.ExampleValidator2"}],
        "custodian_params": {"max_errors": 7, "$scratch_dir": "$CUSTODIAN_TEST_SCRATCH"},
    }
    c = Custodian.from_spec(spec)

    job1, job2 = c.jobs
    assert job1.env == {"A": "foo-value", "B": "plain"}
    assert job2.env == {"A": "$CUSTODIAN_TEST_FOO"}
    assert isinstance(job2.payload, ExampleValidator1)
    assert job1.cmd == job2.cmd == ["run", "foo-value"]
    assert [type(h) for h in c.handlers] == [FlagFileHandler]
    assert c.handlers[0].flag == "stop.flag"
    assert [type(v) for v in c.validators] == [ExampleValidator2]
    assert c.max_errors == 7
    assert c.max_errors_per_job == 7
    assert c.scratch_dir == "/scratch/here"


def test_from_spec_minimal(workdir) -> None:
    c = Custodian.from_spec({"jobs": [{"jb": f"{__name__}.RecordingJob", "params": {"jobid": 5}}]})
    assert c.handlers == []
    assert c.validators == []
    assert c.max_errors == 1
    c.run()
    assert RUN_CALLS == [5]


def test_from_spec_unknown_class_raises() -> None:
    with pytest.raises(AttributeError):
        Custodian.from_spec({"jobs": [{"jb": f"{__name__}.NoSuchJob"}]})


# --------------------------- default Job.terminate --------------------------


class PlainSleepJob(Job):
    """Popen job that does NOT override Job.terminate; first run sleeps, later runs exit at once."""

    def __init__(self, first_sleep=1.0) -> None:
        self.first_sleep = first_sleep
        self.procs: list[subprocess.Popen] = []

    def setup(self, directory="./") -> None:
        pass

    def run(self, directory="./"):
        duration = self.first_sleep if not self.procs else 0
        proc = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({duration})"], cwd=directory)
        self.procs.append(proc)
        return proc

    def postprocess(self, directory="./") -> None:
        pass


def test_job_default_terminate_is_noop() -> None:
    job = PlainSleepJob()
    assert job.terminate() is None
    assert job.terminate(directory="elsewhere") is None
    assert job.name == "PlainSleepJob"


@pytest.mark.xfail(
    strict=True,
    reason="custodian.py:486 `job.terminate or p.terminate` - the base Job.terminate bound method is always "
    "truthy, so the documented Popen.terminate fallback is unreachable and a terminating monitor cannot "
    "kill a job that does not override terminate().",
)
def test_terminating_monitor_kills_job_without_terminate_override(workdir) -> None:
    job = PlainSleepJob(first_sleep=1.0)
    monitor = OneShotMonitor(is_terminating=True)
    c = Custodian([monitor], [job], max_errors=10, polling_time_step=0.02, monitor_freq=2)
    c.run()
    assert len(job.procs) == 2
    # The first process should have been killed by the monitor, not run to a clean exit.
    assert job.procs[0].returncode != 0
