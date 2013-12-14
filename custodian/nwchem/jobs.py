#!/usr/bin/env python

"""
This module implements basic kinds of jobs for Nwchem runs.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "5/20/13"


import subprocess
import shutil

from pymatgen.util.io_utils import zopen
from pymatgen.serializers.json_coders import MSONable

from custodian.custodian import Job, gzip_dir


class NwchemJob(Job, MSONable):
    """
    A basic Nwchem job.
    """

    def __init__(self, nwchem_cmd, input_file="mol.nw",
                 output_file="mol.nwout", gzipped=False,
                 backup=True, settings_override=None):
        """
        Args:
            nwchem_cmd:
                Command to run Nwchem as a list of args. For example,
                ["nwchem"].
            output_file:
                Name of file to direct standard out to.
            backup:
                Boolean whether to backup the initial input files. If True,
                the input files will be copied with a ".orig" appended.
                Defaults to True.
            gzipped:
                Deprecated. Please use the Custodian class's gzipped_output
                option instead. Whether to gzip the final output. Defaults to
                False.
            settings_override:
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
        if self.backup:
            shutil.copy(self.input_file, "{}.orig".format(self.input_file))

    def run(self):
        with zopen(self.output_file, 'w') as fout:
            return subprocess.Popen(self.nwchem_cmd + [self.input_file],
                                    stdout=fout)

    def postprocess(self):
        if self.gzipped:
            gzip_dir(".")

    @property
    def name(self):
        return "Nwchem Job"

    @property
    def to_dict(self):
        d = dict(nwchem_cmd=self.nwchem_cmd, input_file=self.input_file,
                 output_file=self.output_file,
                 gzipped=self.gzipped, backup=self.backup,
                 settings_override=self.settings_override
                 )
        d["@module"] = self.__class__.__module__
        d["@class"] = self.__class__.__name__
        return d

    @classmethod
    def from_dict(cls, d):
        return NwchemJob(
            nwchem_cmd=d["nwchem_cmd"], input_file=d["input_file"],
            output_file=d["output_file"], gzipped=d["gzipped"],
            backup=d["backup"], settings_override=d["settings_override"])
