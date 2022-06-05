import glob
import os
import random
import subprocess
import unittest

from ruamel import yaml

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

    def setup(self):
        pass

    def run(self):
        return subprocess.Popen(f"exit {self.exitcode}", shell=True)

    def postprocess(self):
        pass


class ExampleJob(Job):
    def __init__(self, jobid, params=None):
        if params is None:
            params = {"initial": 0, "total": 0}
        self.jobid = jobid
        self.params = params

    def setup(self):
        self.params["initial"] = 0
        self.params["total"] = 0

    def run(self):
        sequence = [random.uniform(0, 1) for i in range(100)]
        self.params["total"] = self.params["initial"] + sum(sequence)

    def postprocess(self):
        pass

    @property
    def name(self):
        return f"ExampleJob{self.jobid}"


class ExampleHandler(ErrorHandler):
    def __init__(self, params):
        self.params = params

    def check(self):
        return self.params["total"] < 50

    def correct(self):
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

    def check(self):
        return True

    def correct(self):
        self.has_error = True
        return {"errors": "Unrecoverable error", "actions": None}


class ExampleHandler2b(ExampleHandler2):
    """
    This handler always result in an error. No runtime error though
    """

    raises_runtime_error = False

    def correct(self):
        self.has_error = True
        return {"errors": "Unrecoverable error", "actions": []}


class ExampleValidator1(Validator):
    def __init__(self):
        pass

    def check(self):
        return False


class ExampleValidator2(Validator):
    def __init__(self):
        pass

    def check(self):
        return True


class CustodianTest(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    def test_exitcode_error(self):
        c = Custodian([], [ExitCodeJob(0)])
        c.run()
        c = Custodian([], [ExitCodeJob(1)])
        self.assertRaises(ReturnCodeError, c.run)
        self.assertTrue(c.run_log[-1]["nonzero_return_code"])
        c = Custodian([], [ExitCodeJob(1)], terminate_on_nonzero_returncode=False)
        c.run()

    def test_run(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(njobs)],
            max_errors=njobs,
        )
        output = c.run()
        self.assertEqual(len(output), njobs)
        ExampleHandler(params).as_dict()

    def test_run_interrupted(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(njobs)],
            max_errors=njobs,
        )

        self.assertEqual(c.run_interrupted(), njobs)
        self.assertEqual(c.run_interrupted(), njobs)

        total_done = 1
        while total_done < njobs:
            c.jobs[njobs - 1].run()
            if params["total"] > 50:
                self.assertEqual(c.run_interrupted(), njobs - total_done)
                total_done += 1

    def test_unrecoverable(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        h = ExampleHandler2(params)
        c = Custodian([h], [ExampleJob(i, params) for i in range(njobs)], max_errors=njobs)
        self.assertRaises(NonRecoverableError, c.run)
        self.assertTrue(h.has_error)
        h = ExampleHandler2b(params)
        c = Custodian([h], [ExampleJob(i, params) for i in range(njobs)], max_errors=njobs)
        c.run()
        self.assertTrue(h.has_error)
        self.assertEqual(c.run_log[-1]["handler"], h)

    def test_max_errors(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        h = ExampleHandler(params)
        c = Custodian(
            [h],
            [ExampleJob(i, params) for i in range(njobs)],
            max_errors=1,
            max_errors_per_job=10,
        )
        self.assertRaises(MaxCorrectionsError, c.run)
        self.assertTrue(c.run_log[-1]["max_errors"])

    def test_max_errors_per_job(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        h = ExampleHandler(params)
        c = Custodian(
            [h],
            [ExampleJob(i, params) for i in range(njobs)],
            max_errors=njobs,
            max_errors_per_job=1,
        )
        self.assertRaises(MaxCorrectionsPerJobError, c.run)
        self.assertTrue(c.run_log[-1]["max_errors_per_job"])

    def test_max_errors_per_handler_raise(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        h = ExampleHandler1b(params)
        c = Custodian(
            [h],
            [ExampleJob(i, params) for i in range(njobs)],
            max_errors=njobs * 10,
            max_errors_per_job=1000,
        )
        self.assertRaises(MaxCorrectionsPerHandlerError, c.run)
        self.assertEqual(h.n_applied_corrections, 2)
        self.assertEqual(len(c.run_log[-1]["corrections"]), 2)
        self.assertTrue(c.run_log[-1]["max_errors_per_handler"])
        self.assertEqual(c.run_log[-1]["handler"], h)

    def test_max_errors_per_handler_warning(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler1c(params)],
            [ExampleJob(i, params) for i in range(njobs)],
            max_errors=njobs * 10,
            max_errors_per_job=1000,
        )
        c.run()
        self.assertTrue(all(len(r["corrections"]) <= 2 for r in c.run_log))

    def test_validators(self):
        njobs = 100
        params = {"initial": 0, "total": 0}
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(njobs)],
            [ExampleValidator1()],
            max_errors=njobs,
        )
        output = c.run()
        self.assertEqual(len(output), njobs)

        njobs = 100
        params = {"initial": 0, "total": 0}
        v = ExampleValidator2()
        c = Custodian(
            [ExampleHandler(params)],
            [ExampleJob(i, params) for i in range(njobs)],
            [v],
            max_errors=njobs,
        )
        self.assertRaises(ValidationError, c.run)
        self.assertEqual(c.run_log[-1]["validator"], v)

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
        d = yaml.safe_load(spec)
        c = Custodian.from_spec(d)
        self.assertEqual(c.jobs[0].vasp_cmd[2], "whatever")
        self.assertEqual(c.scratch_dir, "/tmp/random")
        self.assertEqual(len(c.jobs), 2)
        self.assertEqual(len(c.handlers), 3)
        self.assertEqual(len(c.validators), 1)

    def tearDown(self):
        for f in glob.glob("custodian.*.tar.gz"):
            os.remove(f)
        try:
            os.remove("custodian.json")
        except OSError:
            pass  # Ignore if file cannot be found.
        os.chdir(self.cwd)


# class CustodianCheckpointTest(unittest.TestCase):
#     def test_checkpoint_loading(self):
#         self.cwd = os.getcwd()
#         pth = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "test_files", "checkpointing")
#         # os.chdir()
#         shutil.copy(os.path.join(pth, "backup.tar.gz"), "custodian.chk.3.tar.gz")
#         njobs = 5
#         params = {"initial": 0, "total": 0}
#         c = Custodian(
#             [ExampleHandler(params)],
#             [ExampleJob(i, params) for i in range(njobs)],
#             [ExampleValidator1()],
#             max_errors=100,
#             checkpoint=True,
#         )
#         self.assertEqual(len(c.run_log), 3)
#         self.assertEqual(len(c.run()), 5)
#         os.remove("custodian.json")
#         os.chdir(self.cwd)


if __name__ == "__main__":
    unittest.main()
