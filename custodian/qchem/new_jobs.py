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

__author__ = "Samuel Blau, Brandon Woods, Shyam Dwaraknath"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/20/18"


class QCJob(Job):
    """
    A basic QChem Job.
    """

    def __init__(self, qchem_command="qchem", multimode="openmp", input_file="mol.qin", output_file="mol.qout", max_cores=32, qclog_file="mol.qclog", gzipped=False, scratch="/dev/shm/qcscratch/", save_scratch=False, save_name="default_save_name"):
        """
        Args:
            qchem_command (str): Command to run QChem.
            multimode (str): Parallelization scheme, either openmp or mpi.
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            max_cores (int): Maximum number of cores to parallelize over. 
                Defaults to 32.
            qclog_file (str): Name of the file to redirect the standard output
                to. None means not to record the standard output. Defaults to
                None.
            gzipped (bool): Whether to gzip the final output. Defaults to False.
            scratch (str): QCSCRATCH directory. Defaults to "/dev/shm/qcscratch/".
            save_scratch (bool): Whether to save scratch directory contents. 
                Defaults to False.
            save_name (str): Name of the saved scratch directory. Defaults to
                to "default_save_name".
        """
        self.qchem_command = qchem_command.split(" ")
        self.multimode = multimode
        self.input_file = input_file
        self.output_file = output_file
        self.max_cores = max_cores
        self.qclog_file = qclog_file
        self.gzipped = gzipped
        self.scratch = scratch
        self.save_scratch = save_scratch
        self.save_name = save_name


    @property
    def current_command(self):
        multimode_index = 1
        if self.save_scratch:
            command = self.qchem_command+["-save","",str(self.max_cores),self.input_file,self.output_file,self.save_name]
            multimode_index = 2
        else:
            command = self.qchem_command+["",str(self.max_cores),self.input_file,self.output_file]
        if self.multimode == 'openmp':
            command[multimode_index] = "-nt"
        elif self.multimode == 'mpi':
            command[multimode_index] = "-np"
        else:
            print("ERROR: Multimode should only be set to openmp or mpi")
        return command


    def setup(self):
        os.putenv("QCSCRATCH",self.scratch)
        if self.multimode == 'openmp':
            os.putenv('QCTHREADS',str(self.max_cores))
            os.putenv('OMP_NUM_THREADS',str(self.max_cores))


    def postprocess(self):
        if self.save_scratch:
            shutil.copytree(os.path.join(self.scratch,self.save_name),
                            os.path.join(os.path.dirname(self.input_file),self.save_name))
        if self.gzipped:
            gzip_dir(".")


    def run(self):
        """
        Perform the actual QChem run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        qclog = open(self.qclog_file, 'w')
        p = subprocess.Popen(self.current_command, stdout=qclog)
        return p



