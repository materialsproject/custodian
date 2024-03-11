import os
import random
import subprocess
import unittest
from glob import glob

import pytest
from ruamel.yaml import YAML

from custodian.custodian import (
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
    def __init__(self, exitcode=0):
        self.exitcode = exitcode

    def setup(self, directory="./"):
        pass

    def run(self, directory="./"):
        return subprocess.Popen(f"exit {self.exitcode}", cwd=directory, shell=True)

    def postprocess(self, directory="./"):
        pass


class ExampleJob(Job):
    def __init__(self, jobid, params=None):
        if params is None:
            params = {"initial": 0, "total": 0}
        self.jobid = jobid
        self.params = params

    def setup(self, directory="./"):
        self.params["initial"] = 0
        self.params["total"] = 0

    def run(self, directory="./"):
        sequence = [random.uniform(0, 1) for i in range(100)]
        self.params["total"] = self.params["initial"] + sum(sequence)

    def postprocess(self, directory="./"):
        pass

    @property
    def name(self):
        return f"ExampleJob{self.jobid}"


class ExampleHandler(ErrorHandler):
    def __init__(self, params):
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

    max_num_corrections = 2  # type: ignore
    raise_on_max = True


class ExampleHandler1c(ExampleHandler):
    """
    This handler always can apply a correction, but will only apply it twice and then not anymore.
    """

    max_num_corrections = 2  # type: ignore
    raise_on_max = False


class ExampleHandler2(ErrorHandler):
    """
    This handler always result in an error.
    """

    def __init__(self, params):
        self.params = params
        self.has_error = False

    def check(self, directory="./"):
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
    def __init__(self):
        pass

    def check(self, directory="./"):
        return False


class ExampleValidator2(Validator):
    def __init__(self):
        pass

    def check(self, directory="./"):
        return True


class CustodianTest(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    def test_exitcode_error(self):
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

    def test_run(self):
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

    def test_run_interrupted(self):
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

    def test_unrecoverable(self):
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

    def test_max_errors(self):
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

    def test_max_errors_per_job(self):
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

    def test_max_errors_per_handler_raise(self):
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

    def test_max_errors_per_handler_warning(self):
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

    def test_validators(self):
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

    def test_from_spec(self):
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

    def tearDown(self):
        for file in glob("custodian.*.tar.gz"):
            os.remove(file)
        try:
            os.remove("custodian.json")
        except OSError:
            pass  # Ignore if file cannot be found.
        os.chdir(self.cwd)


# class TestCustodianCheckpoint:
#     def test_checkpoint_loading(self):
#         self.cwd = os.getcwd()
#         pth = f"{TEST_FILES}/checkpointing"
#         # os.chdir()
#         shutil.copy(os.path.join(pth, "backup.tar.gz"), "custodian.chk.3.tar.gz")
#         n_jobs = 5
#         params = {"initial": 0, "total": 0}
#         c = Custodian(
#             [ExampleHandler(params)],
#             [ExampleJob(i, params) for i in range(n_jobs)],
#             [ExampleValidator1()],
#             max_errors=100,
#             checkpoint=True,
#         )
#         assert len(c.run_log) == 3
#         assert len(c.run()) == 5
#         os.remove("custodian.json")
#         os.chdir(self.cwd)
