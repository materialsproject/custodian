#!/usr/bin/env python

"""
This module implements basic kinds of jobs for Gaussian runs.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "5/20/13"


import subprocess
import os
import shutil

from pymatgen.util.io_utils import zopen
from pymatgen.serializers.json_coders import MSONable

from custodian.custodian import Job


class NwchemJob(Job, MSONable):
    """
    A basic Gaussian job. Just runs whatever is in the directory. But
    conceivably can be a complex processing of inputs etc. with initialization.
    """

    def __init__(self, nwchem_cmd, input_file="mol.nw",
                 output_file="mol.nwout",
                 suffix="", gzipped=False, backup=True,
                 settings_override=None):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors.

        Args:
            nwchem_cmd:
                Command to run Nwchem as a list of args. For example,
                ["nwchem"].
            output_file:
                Name of file to direct standard out to.
            suffix:
                A suffix to be appended to the final output.
            backup:
                Boolean whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
            gzipped:
                Whether to gzip the final output. Defaults to False.
            settings_override:
                An ansible style list of dict to override changes.
                TODO: Not implemented yet.
        """
        self.nwchem_cmd = nwchem_cmd
        self.input_file = input_file
        self.output_file = output_file
        self.backup = backup
        self.gzipped = gzipped
        self.suffix = suffix
        self.settings_override = settings_override

    def setup(self):
        if self.backup:
            shutil.copy(self.input_file, "{}.orig".format(self.input_file))

    def run(self):
        with zopen(self.output_file, 'w') as fout:
            return subprocess.Popen(self.nwchem_cmd + [self.input_file],
                                    stdout=fout)

    def postprocess(self):
        if self.gzipped:
            gzip_directory(".")

    @property
    def name(self):
        return "Nwchem Job"

    @property
    def to_dict(self):
        d = dict(nwchem_cmd=self.nwchem_cmd, input_file=self.input_file,
                 output_file=self.output_file, suffix=self.suffix,
                 gzipped=self.gzipped, backup=self.backup,
                 settings_override=self.settings_override
                 )
        d["@module"] = self.__class__.__module__
        d["@class"] = self.__class__.__name__
        return d

    @staticmethod
    def from_dict(d):
        return NwchemJob(
            nwchem_cmd=d["nwchem_cmd"], input_file=d["input_file"],
            output_file=d["output_file"],
            suffix=d["suffix"], gzipped=d["gzipped"], backup=d["backup"],
            settings_override=d["settings_override"])


def gzip_directory(path):
    """
    Gzips all files in a directory.

    Args:
        path:
            Path to directory.
    """
    for f in os.listdir(path):
        if not f.endswith("gz"):
            with zopen(f, 'rb') as f_in, \
                    zopen('{}.gz'.format(f), 'wb') as f_out:
                f_out.writelines(f_in)
            os.remove(f)

