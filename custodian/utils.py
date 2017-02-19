# coding: utf-8

from __future__ import unicode_literals, division

"""
Utility function and classes.
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__date__ = "1/12/14"

from glob import glob
import logging
import os
import tarfile
import re
import shlex
import subprocess


def backup(filenames, prefix="error"):
    """
    Backup files to a tar.gz file. Used, for example, in backing up the
    files of an errored run before performing corrections.

    Args:
        filenames ([str]): List of files to backup. Supports wildcards, e.g.,
            *.*.
        prefix (str): prefix to the files. Defaults to error, which means a
            series of error.1.tar.gz, error.2.tar.gz, ... will be generated.
    """
    num = max([0] + [int(f.split(".")[1])
                     for f in glob("{}.*.tar.gz".format(prefix))])
    filename = "{}.{}.tar.gz".format(prefix, num + 1)
    logging.info("Backing up run to {}.".format(filename))
    with tarfile.open(filename, "w:gz") as tar:
        for fname in filenames:
            for f in glob(fname):
                tar.add(f)


def get_execution_host_info():
    """
    Tries to return a tuple describing the execution host.
    Doesn't work for all queueing systems

    Returns:
        (HOSTNAME, CLUSTER_NAME)
    """
    host = os.environ.get('HOSTNAME', None)
    cluster = os.environ.get('SGE_O_HOST', None)
    if host is None:
        try:
            import socket
            host = host or socket.gethostname()
        except:
            pass
    return host or 'unknown', cluster or 'unknown'


class Terminator:
    """
    A tool to cancel a job step in a SLURM srun job using scancel command.
    """

    def __init__(self, mpi_cmd=None, stderr_filename=None):
        """
        Args:
            stderr_filename: The file name of the stderr for srun job step.
        """
        self.mpi_cmd = mpi_cmd
        self.stderr_filename = stderr_filename

    def run(self):
        if self.mpi_cmd == "sun":
            self.stderr_filename = self.stderr_filename or "std_err.txt"
            step_id = self.parse_srun_step_number()
            scancel_cmd = shlex.split("scancel --signal=KILL {}".format(step_id))
            logging.info("Terminate the job step using {}".format(' '.join(scancel_cmd)))
            subprocess.Popen(scancel_cmd)
        else:
            return None

    def parse_srun_step_number(self):
        step_pat_text = r"srun: launching (?P<step_id>\d+[.]\d+) on host \w+, \d+ tasks:"
        step_pat = re.compile(step_pat_text)
        step_id = None
        with open(self.stderr_filename) as f:
            err_text = f.readlines()
        for line in err_text:
            m = step_pat.search(line)
            if m is not None:
                step_id = m.group("step_id")
        if step_id is None:
            raise ValueError("Can't find SRUN job step number in STDERR file")
        return step_id
