# coding: utf-8

from __future__ import unicode_literals, division
import subprocess
import os
import shutil
import math
import logging

import numpy as np

from pymatgen import Structure
from monty.os.path import which
from monty.shutil import decompress_dir
from monty.serialization import dumpfn, loadfn

from custodian.custodian import Job
from pymatgen.io.cp2k.inputs import Cp2kInput

"""
This module implements basic kinds of jobs for Cp2k runs.
"""


logger = logging.getLogger(__name__)


__author__ = "Nicholas Winner"
__version__ = "0.1"

CP2K_INPUT_FILES = ["cp2k.inp"]

CP2K_OUTPUT_FILES = ['cp2k.out']


class Cp2kJob(Job):
    """
    A basic cp2k job. Just runs whatever is in the directory. But conceivably
    can be a complex processing of inputs etc. with initialization.
    """

    def __init__(self, cp2k_cmd, input_file="cp2k.inp", output_file="cp2k.out",
                 stderr_file="std_err.txt", suffix="", final=True,
                 backup=True, settings_override=None):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors. The defaults are usually fine too.

        Args:
            cp2k_cmd (str): Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            input_file (str): Name of the file to use as input to CP2K
                executable. Defaults to "cp2k.inp"
            output_file (str): Name of file to direct standard out to.
                Defaults to "cp2k.out".
            stderr_file (str): Name of file to direct standard error to.
                Defaults to "std_err.txt".
            suffix (str): A suffix to be appended to the final output. E.g.,
                to rename all CP2K output from say cp2k.out to
                cp2k.out.relax1, provide ".relax1" as the suffix.
            final (bool): Indicating whether this is the final cp2k job in a
                series. Defaults to True.
            backup (bool): Whether to backup the initial input files. If True,
                the input file will be copied with a
                ".orig" appended. Defaults to True.
            settings_override ([dict]): An ansible style list of dict to
                override changes. For example, to set spin polarization to
                True for subsequent runs and to copy the CONTCAR to the POSCAR, you will provide::

        """
        self.cp2k_cmd = cp2k_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.final = final
        self.backup = backup
        self.suffix = suffix
        self.settings_override = settings_override

    def setup(self):
        """
        Performs initial setup for Cp2k, including overriding any settings
        and backing up.
        """
        decompress_dir('.')

        if self.settings_override is not None:
            new_input = Cp2kInput.from_file(self.input_file)
            new_input.update(self.settings_override)
            new_input.write_file(self.input_file)

        if self.backup:
            shutil.copy(self.input_file, "{}.orig".format(self.input_file))

    def run(self):
        """
        Perform the actual CP2K run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        cmd = list(self.cp2k_cmd)
        cmd.extend(['-i', self.input_file])
        logger.info("Running {}".format(" ".join(cmd)))
        with open(self.output_file, 'w') as f_std, \
                open(self.stderr_file, "w", buffering=1) as f_err:
            # use line buffering for stderr
            p = subprocess.Popen(cmd, stdout=f_std, stderr=f_err, shell=False)
        return p

    def postprocess(self):
        """
        Postprocessing includes renaming and gzipping where necessary.
        Also copies the magmom to the incar if necessary
        """
        if os.path.exists(self.output_file):
            if self.final and self.suffix != "":
                shutil.move(self.output_file, "{}{}".format(self.output_file, self.suffix))
            elif self.suffix != "":
                shutil.copy(self.output_file, "{}{}".format(self.output_file, self.suffix))

        # Remove continuation so if a subsequent job is run in
        # the same directory, will not restart this job.
        if os.path.exists("continue.json"):
            os.remove("continue.json")

    def terminate(self):
        for k in self.cp2k_cmd:
            if "cp2k" in k:
                try:
                    os.system("killall %s" % k)
                except:
                    pass
