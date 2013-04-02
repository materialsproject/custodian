#!/usr/bin/env python

"""
This module implements basic kinds of jobs for VASP runs.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "2/4/13"


import subprocess
import os
import shutil

from pymatgen.util.io_utils import zopen
from pymatgen.io.vaspio.vasp_input import VaspInput
from pymatgen.io.smartio import read_structure
from pymatgen.io.vaspio_set import MITVaspInputSet
from pymatgen.serializers.json_coders import MSONable, PMGJSONDecoder

from custodian.ansible.intepreter import Modder
from custodian.ansible.actions import FileActions, DictActions
from custodian.custodian import Job


VASP_INPUT_FILES = {"INCAR", "POSCAR", "POTCAR", "KPOINTS"}

VASP_OUTPUT_FILES = ['DOSCAR', 'INCAR', 'KPOINTS', 'POSCAR', 'PROCAR',
                     'vasprun.xml', 'CHGCAR', 'CHG', 'EIGENVAL', 'OSZICAR',
                     'WAVECAR', 'CONTCAR', 'IBZKPT', 'OUTCAR']


class VaspJob(Job, MSONable):
    """
    A basic vasp job. Just runs whatever is in the directory. But conceivably
     can be a complex processing of inputs etc. with initialization.
    """

    def __init__(self, vasp_command, output_file="vasp.out", suffix="",
                 final=True, gzipped=False, backup=True,
                 default_vasp_input_set=MITVaspInputSet(),
                 settings_override=None):
        """
        This constructor is necessarily complex due to the need for
        flexibility. For standard kinds of runs, it's often better to use one
        of the static constructors.

        Args:
            vasp_command:
                Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            output_file:
                Name of file to direct standard out to. Defaults to vasp.out.
            suffix:
                A suffix to be appended to the final output. E.g.,
                to rename all VASP output from say vasp.out to
                vasp.out.relax1, provide ".relax1" as the suffix.
            final:
                Boolean indicating whether this is the final vasp job in a
                series. Defaults to True.
            backup:
                Boolean whether to backup the initial input files. If True,
                the INCAR, KPOINTS, POSCAR and POTCAR will be copied with a
                ".orig" appended. Defaults to True.
            gzipped:
                Whether to gzip the final output. Defaults to False.
            default_vasp_input_set:
                Species the default input set to use for directories that do
                not contain full set of VASP input files. For example,
                if a directory contains only a POSCAR or a cif,
                the vasp input set will be used to generate the necessary
                input files for the run. If the directory already
                contain a full set of VASP input files,
                this input is ignored. Defaults to the MITVaspInputSet.
            settings_override:
                An ansible style list of dict to override changes. For example,
                to set ISTART=1 for subsequent runs and to copy the CONTCAR
                to the POSCAR, you will provide::

                    [{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
                     {"filename": "CONTCAR",
                      "action": {"_file_copy": {"dest": "POSCAR"}}}]
        """
        self.vasp_command = vasp_command
        self.output_file = output_file
        self.final = final
        self.backup = backup
        self.gzipped = gzipped
        self.default_vis = default_vasp_input_set
        self.suffix = suffix
        self.settings_override = settings_override

    def setup(self):
        files = os.listdir(".")
        num_structures = 0
        if not set(files).issuperset(VASP_INPUT_FILES):
            for f in files:
                try:
                    struct = read_structure(f)
                    num_structures += 1
                except:
                    pass
            if num_structures != 1:
                raise RuntimeError("{} structures found. Unable to continue."
                                   .format(num_structures))
            else:
                self.default_vis.write_input(struct, ".")

        if self.backup:
            for f in VASP_INPUT_FILES:
                shutil.copy(f, "{}.orig".format(f))

        if self.settings_override is not None:
            vi = VaspInput.from_directory(".")
            m = Modder([FileActions, DictActions])
            modified = []
            for a in self.settings_override:
                if "dict" in a:
                    modified.append(a["dict"])
                    vi[a["dict"]] = m.modify_object(a["action"],
                                                    vi[a["dict"]])
                elif "filename" in a:
                    m.modify(a["action"], a["filename"])
            for f in modified:
                vi[f].write_file(f)

    def run(self):
        with open(self.output_file, 'w') as f:
            return subprocess.Popen(self.vasp_command, stdout=f)

    def postprocess(self):
        for f in VASP_OUTPUT_FILES + [self.output_file]:
            if os.path.exists(f):
                if self.final and self.suffix != "":
                    shutil.move(f, "{}{}".format(f, self.suffix))
                elif self.suffix != "":
                    shutil.copy(f, "{}{}".format(f, self.suffix))

        if self.gzipped:
            gzip_directory(".")

    @property
    def name(self):
        return "Vasp Job"

    @staticmethod
    def double_relaxation_run(vasp_command, gzipped=True):
        """
        Returns a list of two jobs corresponding to an AFLOW style double
        relaxation run.

        Args:
            vasp_command:
                Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]

        Returns:
            List of two jobs corresponding to an AFLOW style run.
        """
        return [VaspJob(vasp_command, final=False, suffix=".relax1"),
                VaspJob(
                    vasp_command, final=True, backup=False,
                    suffix=".relax2", gzipped=gzipped,
                    settings_override=[
                        {"dict": "INCAR",
                         "action": {"_set": {"ISTART": 1}}},
                        {"filename": "CONTCAR",
                         "action": {"_file_copy": {"dest": "POSCAR"}}}])]

    @property
    def to_dict(self):
        d = dict(vasp_command=self.vasp_command,
                 output_file=self.output_file, suffix=self.suffix,
                 final=self.final, gzipped=self.gzipped, backup=self.backup,
                 default_vasp_input_set=self.default_vis.to_dict,
                 settings_override=self.settings_override
                 )
        d["@module"] = self.__class__.__module__
        d["@class"] = self.__class__.__name__
        return d

    @staticmethod
    def from_dict(d):
        vis = PMGJSONDecoder().process_decoded(d["default_vasp_input_set"])
        return VaspJob(
            vasp_command=d["vasp_command"], output_file=d["output_file"],
            suffix=d["suffix"], final=d["final"], gzipped=d["gzipped"],
            backup=d["backup"], default_vasp_input_set=vis,
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