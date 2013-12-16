#!/usr/bin/env python

"""
This module implements basic kinds of jobs for QChem runs.
"""

from __future__ import division
import os
from pymatgen import zopen
from pymatgen.serializers.json_coders import MSONable
import shutil
import copy
import subprocess
from custodian.custodian import Job, gzip_dir

__author__ = "Xiaohui Qu"
__version__ = "0.1"
__maintainer__ = "Xiaohui Qu"
__email__ = "xhqu1981@gmail.com"
__status__ = "Alpha"
__date__ = "12/03/13"


class QchemJob(Job, MSONable):
    """
    A basis QChem Job.
    """

    def __init__(self, qchem_cmd, input_file="mol.qcinp",
                 output_file="mol.qcout", chk_file=None, qclog_file=None,
                 gzipped=False, backup=True):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors.

        Args:
            qchem_cmd:
                Command to run QChem as a list args (without input/output file
                name). For example: ["qchem", "-np", "24"]
            input_file:
                Name of the QChem input file.
            output_file:
                Name of the QChem output file.
            chk_file:
                Name of the QChem check point file. None means no checkpoint
                point file. Defaults to None.
            qclog_file:
                Name of the file to redirect the standard output to. None means
                not to record the standard output. Defaults to None.
            gzipped:
                Whether to gzip the final output. Defaults to False.
            backup:
                Boolean whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
        """
        self.qchem_cmd = qchem_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.chk_file = chk_file
        self.qclog_file = qclog_file
        self.gzipped = gzipped
        self.backup = backup

    def setup(self):
        if self.backup:
            i = 0
            while os.path.exists("{}.{}.orig".format(self.input_file, i)):
                i += 1
            shutil.copy(self.input_file,
                        "{}.{}.orig".format(self.input_file, i))
            if self.chk_file and os.path.exists(self.chk_file):
                shutil.copy(self.chk_file,
                            "{}.{}.orig".format(self.chk_file, i))
            if os.path.exists(self.output_file):
                shutil.copy(self.output_file,
                            "{}.{}.orig".format(self.output_file, i))
            if self.qclog_file and os.path.exists(self.qclog_file):
                shutil.copy(self.qclog_file,
                            "{}.{}.orig".format(self.qclog_file, i))

    def run(self):
        cmd = copy.deepcopy(self.qchem_cmd)
        cmd += [self.input_file, self.output_file]
        if self.chk_file:
            cmd.append(self.chk_file)
        if self.qclog_file:
            with zopen(self.qclog_file, "w") as filelog:
                returncode = subprocess.call(cmd, stdout=filelog)
        else:
            returncode = subprocess.call(cmd)
        return returncode

    def postprocess(self):
        if self.gzipped:
            gzip_dir(".")

    @property
    def name(self):
        return "QChem Job"

    @property
    def to_dict(self):
        d = dict(qchem_cmd=self.qchem_cmd, input_file=self.input_file,
                 output_file=self.output_file, chk_file=self.chk_file,
                 qclog_file=self.qclog_file, gzipped=self.gzipped,
                 backup=self.backup)
        d["@module"] = self.__class__.__module__
        d["@class"] = self.__class__.__name__
        return d

    @staticmethod
    def from_dict(cls, d):
        return QchemJob(qchem_cmd=d["qchem_cmd"], input_file=d["input_file"],
                        output_file=d["output_file"], chk_file=d["chk_file"],
                        qclog_file=d["qclog_file"], gzipped=d["gzipped"],
                        backup=d["backup"])
