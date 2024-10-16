"""This module implements basic kinds of jobs for JDFTx runs."""

import logging
import os
import shlex
import subprocess

import psutil

from custodian.custodian import Job

logger = logging.getLogger(__name__)


class JDFTxJob(Job):
    """A basic JDFTx job. Runs whatever is in the working directory."""

    def __init__(
        self,
        jdftx_cmd,
        input_file="init.in",
        output_file="jdftx.out",
        stderr_file="std_err.txt",
    ) -> None:
        """
        Args:
            jdftx_cmd (str): Command to run JDFTx as a string.
            input_file (str): Name of the file to use as input to JDFTx
                executable. Defaults to "init.in"
            output_file (str): Name of file to direct standard out to.
                Defaults to "jdftx.out".
            stderr_file (str): Name of file to direct standard error to.
                Defaults to "std_err.txt".
        """
        self.jdftx_cmd = jdftx_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file

    def setup(self, directory="./") -> None:
        """No setup required."""

    def run(self, directory="./"):
        """
        Perform the actual JDFTx run.

        Returns:
        -------
            (subprocess.Popen) Used for monitoring.
        """
        cmd = self.jdftx_cmd + " -i " + self.input_file + " -o " + self.output_file
        logger.info(f"Running {cmd}")
        with (
            open(os.path.join(directory, self.output_file), "w") as f_std,
            open(os.path.join(directory, self.stderr_file), "w", buffering=1) as f_err,
        ):
            # use line buffering for stderr
            return subprocess.run(
                shlex.split(cmd),
                cwd=directory,
                stdout=f_std,
                stderr=f_err,
                shell=False,
                check=False,
            )

    def postprocess(self, directory="./") -> None:
        """No post-processing required."""

    def terminate(self, directory="./") -> None:
        """Terminate JDFTx."""
        work_dir = directory
        logger.info(f"Killing JDFTx processes in {work_dir=}.")
        for proc in psutil.process_iter():
            try:
                if "jdftx" in proc.name():
                    print("name:", proc.name())
                    open_paths = [file.path for file in proc.open_files()]
                    run_path = os.path.join(work_dir, self.output_file)
                    if (run_path in open_paths) and psutil.pid_exists(proc.pid):
                        self.terminate_process(proc)
                        return
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Exception {e} encountered while killing JDFTx.")
                continue

        logger.warning(
            f"Killing JDFTx processes in {work_dir=} failed with subprocess.Popen.terminate(). Resorting to 'killall'."
        )
        cmd = self.jdftx_cmd
        print("cmd:", cmd)
        if "jdftx" in cmd:
            subprocess.run(["killall", f"{cmd}"], check=False)

    @staticmethod
    def terminate_process(proc, timeout=5):
        """Terminate a process gracefully, then forcefully if necessary."""
        try:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except psutil.TimeoutExpired:
                # If process is still running after the timeout, kill it
                logger.warning(f"Process {proc.pid} did not terminate gracefully, killing it.")
                proc.kill()
                # proc.wait()
            else:
                logger.info(f"Process {proc.pid} terminated gracefully.")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Error while terminating process {proc.pid}: {e}")
