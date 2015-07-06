# coding: utf-8

__author__ = 'ndardenne'

import subprocess
import shutil

from monty.io import zopen

from custodian.custodian import Job






class GaussianJob(Job):
    """
    A basic gaussian job to be used inside Custodian (took from the structure of NWChem job)
    """

    def __init__(self, gaussian_cmd="g09", input_file="mol.gau",
                 output_file="mol.log", backup=True):
        """
        Initializes a basic Gaussian job.

        Args:
            gaussian_cmd ([str]): Command to run Gaussian as a list of args. For
                example, ["gaussian"].
            input_file (str): Input file to run. Defaults to "mol.nw".
            output_file (str): Name of file to direct standard out to.
                Defaults to "mol.log".
            backup (bool): Whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.

        """
        self.gaussian_cmd = gaussian_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.backup = backup


    def setup(self):
        """
        Performs backup if necessary.
        """
        if self.backup:
            shutil.copy(self.input_file, "{}.orig".format(self.input_file))

    def run(self):
        """
        Performs actual gaussian run.
        """
        with zopen(self.output_file, 'w') as fout:
            return subprocess.Popen([self.gaussian_cmd, self.input_file],
                                    stdout=fout)

    def postprocess(self):
        """
        to do
        """
        pass





