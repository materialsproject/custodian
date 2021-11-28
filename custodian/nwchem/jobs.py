"""
This module implements basic kinds of jobs for Nwchem runs.
"""

import shutil
import subprocess

from monty.io import zopen
from monty.shutil import gzip_dir

from custodian.custodian import Job

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__status__ = "Beta"
__date__ = "5/20/13"


class NwchemJob(Job):
    """
    A basic Nwchem job.
    """

    def __init__(
        self,
        nwchem_cmd,
        input_file="mol.nw",
        output_file="mol.nwout",
        gzipped=False,
        backup=True,
        settings_override=None,
    ):
        """
        Initializes a basic NwChem job.

        Args:
            nwchem_cmd ([str]): Command to run Nwchem as a list of args. For
                example, ["nwchem"].
            input_file (str): Input file to run. Defaults to "mol.nw".
            output_file (str): Name of file to direct standard out to.
                Defaults to "mol.nwout".
            backup (bool): Whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
            gzipped (bool): Deprecated. Please use the Custodian class's
                gzipped_output option instead.
            settings_override ([dict]):
                An ansible style list of dict to override changes.
                #TODO: Not implemented yet.
        """
        self.nwchem_cmd = nwchem_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.backup = backup
        self.gzipped = gzipped
        self.settings_override = settings_override

    def setup(self):
        """
        Performs backup if necessary.
        """
        if self.backup:
            shutil.copy(self.input_file, f"{self.input_file}.orig")

    def run(self):
        """
        Performs actual nwchem run.
        """
        with zopen(self.output_file, "w") as fout:
            return subprocess.Popen(self.nwchem_cmd + [self.input_file], stdout=fout)  # pylint: disable=R1732

    def postprocess(self):
        """
        Renaming or gzipping as needed.
        """
        if self.gzipped:
            gzip_dir(".")
