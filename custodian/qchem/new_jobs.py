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

    def __init__(self, multimode="openmp", input_file="mol.qin", output_file="mol.qout", max_cores=32, qclog_file="mol.qclog", gzipped=False, backup=True, scratch="/dev/shm/qcscratch/", save=False, save_name="default_save_name"):
        """
        Args:
            multimode (str): Parallelization scheme, either openmp or mpi
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            max_cores (int): Maximum number of cores to parallelize over. 
                Defaults to 32.
            qclog_file (str): Name of the file to redirect the standard output
                to. None means not to record the standard output. Defaults to
                None.
            gzipped (bool): Whether to gzip the final output. Defaults to False.
            backup (bool): Whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
            scratch (str): QCSCRATCH directory. Defaults to "/dev/shm/qcscratch/".
            save (bool): Whether to save scratch directory contents. Defaults
                to False
            save_name (str): Name of the saved scratch directory. Defaults to
                to "default_save_name"
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
        self.save_name = save_name


    @property
    def current_command(self):
        command = ["qchem","","",str(self.max_cores),self.input_file,self.output_file,""]
        if self.save:
            command[1] = "-save"
            command[6] = self.save_name
        if self.multimode == 'openmp':
            command[2] = "-nt"
        elif self.multimode == 'mpi':
            command[2] = "-np"
        else:
            print("ERROR: Multimode should only be set to openmp or mpi")
        
        return command


    def setup(self):
        os.putenv("QCSCRATCH",temp_dir)
        if self.multimode == 'openmp':
            os.putenv('QCTHREADS',str(self.max_cores))
            os.putenv('OMP_NUM_THREADS',str(self.max_cores))


    def postprocess(self):
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



