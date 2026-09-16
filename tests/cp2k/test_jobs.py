# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import os
import signal
import subprocess
import unittest
import warnings
from glob import glob
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

from custodian.cp2k.jobs import Cp2kJob
from custodian.custodian import Custodian
from tests.conftest import TEST_FILES

MODULE_DIR = Path(__file__).resolve().parent
TEST_FILES_DIR = f"{TEST_FILES}/cp2k"

cwd = os.getcwd()


def clean_dir(folder) -> None:
    for file in glob(os.path.join(folder, "error.*.tar.gz")):
        os.remove(file)
    for file in glob(os.path.join(folder, "custodian.chk.*.tar.gz")):
        os.remove(file)


class HandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore")

        clean_dir(TEST_FILES_DIR)

        self.input_file = f"{TEST_FILES_DIR}/cp2k.inp"
        self.input_file_hybrid = f"{TEST_FILES_DIR}/cp2k.inp.hybrid"
        self.output_file = f"{TEST_FILES_DIR}/cp2k.out.test"
        self.std_err = f"{TEST_FILES_DIR}/std_err.tmp"
        self.logfile = f"{TEST_FILES_DIR}/custodian.json"

        if os.path.isfile(Custodian.LOG_FILE):
            os.remove("custodian.json")
        if os.path.isfile(self.std_err):
            os.remove(self.std_err)
        if os.path.isfile(self.output_file):
            os.remove(self.output_file)

    def test_job(self) -> None:
        job = Cp2kJob(
            cp2k_cmd=["echo"],
            input_file=self.input_file,
            output_file=self.output_file,
            stderr_file=self.std_err,
            suffix="",
            final=True,
            backup=False,
            settings_override=None,
        )
        c = Custodian(jobs=[job], handlers=[])
        c.run()
        if os.path.isfile(Custodian.LOG_FILE):
            os.remove("custodian.json")
        if os.path.isfile(self.std_err):
            os.remove(self.std_err)

    def test_double(self) -> None:
        jobs = Cp2kJob.double_job(
            cp2k_cmd=["echo"],
            input_file=self.input_file_hybrid,
            output_file=self.output_file,
            stderr_file="std_err.tmp",
            backup=False,
        )
        assert len(jobs) == 2


class TestCp2kJobTerminate(unittest.TestCase):
    def test_run_starts_new_session_and_stores_process(self) -> None:
        process = Mock()
        job = Cp2kJob(cp2k_cmd=["srun", "cp2k.popt"], backup=False)

        with (
            TemporaryDirectory() as directory,
            patch("custodian.cp2k.jobs.subprocess.Popen", return_value=process) as popen,
        ):
            result = job.run(directory)

        assert result is process
        assert job._cp2k_process is process
        assert popen.call_args.kwargs["start_new_session"] is True

    def test_already_finished(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = 0
        job = Cp2kJob(cp2k_cmd=["srun", "cp2k.popt"])
        job._cp2k_process = process

        with patch("custodian.cp2k.jobs.os.killpg", create=True) as killpg:
            job.terminate()

        killpg.assert_not_called()
        process.terminate.assert_not_called()

    def test_posix_sigterm_terminates_job_process_group(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = None
        job = Cp2kJob(cp2k_cmd=["srun", "cp2k.popt"])
        job._cp2k_process = process

        with (
            patch("custodian.cp2k.jobs.os.name", "posix"),
            patch("custodian.cp2k.jobs.os.getpgid", return_value=67890, create=True),
            patch("custodian.cp2k.jobs.os.killpg", create=True) as killpg,
        ):
            job.terminate()

        killpg.assert_called_once_with(67890, signal.SIGTERM)
        process.wait.assert_called_once_with(timeout=10.0)
        process.terminate.assert_not_called()

    def test_posix_escalates_to_sigkill_after_timeout(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("cp2k", 2.5), None]
        job = Cp2kJob(cp2k_cmd=["srun", "cp2k.popt"], terminate_timeout=2.5)
        job._cp2k_process = process

        with (
            patch("custodian.cp2k.jobs.os.name", "posix"),
            patch("custodian.cp2k.jobs.os.getpgid", return_value=67890, create=True),
            patch("custodian.cp2k.jobs.os.killpg", create=True) as killpg,
            patch("custodian.cp2k.jobs.signal.SIGKILL", 9, create=True),
        ):
            job.terminate()

        assert killpg.call_args_list == [
            call(67890, signal.SIGTERM),
            call(67890, 9),
        ]
        assert process.wait.call_count == 2
        process.terminate.assert_not_called()

    def test_windows_fallback_terminates_only_launcher(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = None
        job = Cp2kJob(cp2k_cmd=["mpiexec", "cp2k.psmp"])
        job._cp2k_process = process

        with (
            patch("custodian.cp2k.jobs.os.name", "nt"),
            patch("custodian.cp2k.jobs.os.killpg", create=True) as killpg,
        ):
            job.terminate()

        killpg.assert_not_called()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=10.0)

    def test_parent_fallback_escalates_to_kill(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("cp2k", 10.0), None]
        job = Cp2kJob(cp2k_cmd=["mpiexec", "cp2k.psmp"])
        job._cp2k_process = process

        with patch("custodian.cp2k.jobs.os.name", "nt"):
            job.terminate()

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        assert process.wait.call_count == 2
