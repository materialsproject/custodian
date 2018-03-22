# coding: utf-8

from __future__ import unicode_literals, division
import glob
import logging
import shlex
import socket
import re
import time

"""
New QChem job module
"""

import os
import shutil
import copy
import subprocess
from monty.tempfile import ScratchDir
from pymatgen.io.qchem_io.inputs import QCInput
from pymatgen.io.qchem_io.outputs import QCOutput
from custodian.custodian import Job, gzip_dir

__author__ = "Samuel Blau"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/20/18"


class QCJob(Job):
    """
    A basic QChem Job.
    """

    def __init__(self, multimode="openmp", input_file="mol.qin", output_file="mol.qout", max_cores=32, qclog_file=None, gzipped=False, backup=True, scratch="/dev/shm/qcscratch/", save=False):
        """
        Args:
            multimode (str): Parallelization scheme, either openmp or mpi
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            max_cores (str): Maximum number of cores to parallelize over. 
                Defaults to 32.
            qclog_file (str): Name of the file to redirect the standard output
                to. None means not to record the standard output. Defaults to
                None.
            gzipped (bool): Whether to gzip the final output. Defaults to False.
            backup (bool): Whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
            scratch (str): QCSCRATCH directory. Defaults to "/dev/shm/qcscratch/".
            save (bool): Whether to save scratch directory contents. 
                Defaults to False
        """
        self.multimode = multimode
        self.input_file = input_file
        self.output_file = output_file
        self.max_cores = max_cores
        self.qclog_file = qclog_file
        self.gzipped = gzipped
        self.backup = backup
        self.scratch = scratch
        self.save = save


    @property
    def current_command(self):
        command = ["qchem","",str(self.max_cores),self.input_file,self.output_file]
        if self.multimode == 'openmp':
            os.putenv('QCTHREADS',str(self.max_cores))
            command[1] = "-nt"
        elif self.multimode == 'mpi':
            command[1] = "-np"
        else:
            print "ERROR: Multimode should only be set to openmp or mpi"
        return command


    def setup(self):
        if self.backup:
            i = 0
            while os.path.exists("{}.{}.orig".format(self.input_file, i)):
                i += 1
            shutil.copy(self.input_file,
                        "{}.{}.orig".format(self.input_file, i))
            if os.path.exists(self.output_file):
                shutil.copy(self.output_file,
                            "{}.{}.orig".format(self.output_file, i))
            if self.qclog_file and os.path.exists(self.qclog_file):
                shutil.copy(self.qclog_file,
                            "{}.{}.orig".format(self.qclog_file, i))


    def postprocess(self):
        if self.gzipped:
            gzip_dir(".")


    def run(self):
        """
        Sets up a symbolic link to a scratch directory, sets the
        QCSCRATCH environment variable, and calls _run_qchem().
        """
        with ScratchDir(self.scratch, create_symbolic_link=True,
                        copy_to_current_on_exit=self.save,
                        copy_from_current_on_enter=False) as temp_dir:
            os.putenv("QCSCRATCH",temp_dir)
            self._run_qchem()


    def _run_qchem(self):
        """
        Perform the actual QChem run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        qclog = open(self.qclog_file, 'w')
        p = subprocess.Popen(self.current_command, stdout=qclog)
        return p



