"""This module implements jobs for Lobster runs. """

import logging
import os
import shutil
import subprocess

from monty.io import zopen
from monty.shutil import compress_file

from custodian.custodian import Job

__author__ = "Janine George, Guido Petretto,Aakash Naik"
__copyright__ = "Copyright 2020, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Janine George"
__email__ = "janine.george@uclouvain.be"
__date__ = "April 27, 2020"

LOBSTERINPUT_FILES = ["lobsterin"]
LOBSTEROUTPUT_FILES = [
    "lobsterout",
    "CHARGE.lobster",
    "COHPCAR.lobster",
    "COOPCAR.lobster",
    "DOSCAR.lobster",
    "GROSSPOP.lobster",
    "ICOHPLIST.lobster",
    "ICOOPLIST.lobster",
    "lobster.out",
    "projectionData.lobster",
    "MadelungEnergies.lobster",
    "SitePotentials.lobster",
    "bandOverlaps.lobster",
    "ICOBILIST.lobster",
    "COBICAR.lobster",
    "DOSCAR.LSO.lobster",
]
FW_FILES = ["custodian.json", "FW.json", "FW_submit.script"]

logger = logging.getLogger(__name__)


class LobsterJob(Job):
    """
    Runs the Lobster Job
    """

    def __init__(
        self,
        lobster_cmd: str,
        output_file: str = "lobsterout",
        stderr_file: str = "std_err_lobster.txt",
        gzipped: bool = True,
        add_files_to_gzip=[],
        backup: bool = True,
    ):
        """

        Args:
            lobster_cmd: command to run lobster
            output_file: usually lobsterout
            stderr_file: standard output
            gzipped: if True, Lobster files and add_files_to_gzip will be gzipped
            add_files_to_gzip: list of files that should be gzipped
            backup: if True, lobsterin will be copied to lobsterin.orig
        """
        self.lobster_cmd = lobster_cmd
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.gzipped = gzipped
        self.add_files_to_gzip = add_files_to_gzip
        self.backup = backup

    def setup(self):
        """
        will backup lobster input files
        """
        if self.backup:
            for f in LOBSTERINPUT_FILES:
                shutil.copy(f, f"{f}.orig")

    def run(self):
        """
        runs the job
        """
        cmd = self.lobster_cmd

        logger.info(f"Running {' '.join(cmd)}")

        with zopen(self.output_file, "w") as f_std, zopen(self.stderr_file, "w", buffering=1) as f_err:
            # use line buffering for stderr
            return subprocess.Popen(cmd, stdout=f_std, stderr=f_err)  # pylint: disable=R1732

    def postprocess(self):
        """
        will gzip relevant files (won't gzip custodian.json and other output files from the cluster)
        """
        if self.gzipped:
            for file in LOBSTEROUTPUT_FILES:
                if os.path.exists(file):
                    compress_file(file, compression="gz")
            for file in LOBSTERINPUT_FILES:
                if os.path.exists(file):
                    compress_file(file, compression="gz")
            if self.backup:
                if os.path.exists("lobsterin.orig"):
                    compress_file("lobsterin.orig", compression="gz")
            for file in FW_FILES:
                if os.path.exists(file):
                    compress_file(file, compression="gz")
            for file in self.add_files_to_gzip:
                compress_file(file, compression="gz")
