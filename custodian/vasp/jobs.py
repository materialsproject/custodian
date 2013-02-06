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
from pymatgen.io.vaspio.vasp_input import Incar, Poscar
from pymatgen.io.cifio import CifParser
from pymatgen.io.vaspio_set import MITVaspInputSet

from custodian.custodian import Job


class BasicVaspJob(Job):
    """
    A basic vasp job. Just runs whatever is in the directory. But
    conceivably can be a complex processing of inputs etc. with initialization.
    """

    def __init__(self, vasp_command, output_file="vasp.out",
                 default_vasp_input_set=MITVaspInputSet()):
        """
        Args:
            vasp_command:
                Command to run vasp as a list of args. For example,
                if you are using mpirun, it can be something like
                ["mpirun", "pvasp.5.2.11"]
            output_file:
                Name of file to direct standard out to. Defaults to vasp.out.
            default_vasp_input_set:
                Species the default input set to use for directories that do
                not contain full set of VASP input files. For example,
                if a directory contains only a POSCAR or a cif,
                the vasp input set will be used to generate the necessary
                input files for the run. If the directory already
                contain a full set of VASP input files,
                this input is ignored. Defaults to the MITVaspInputSet.
        """
        self.vasp_command = vasp_command
        self.output_file = output_file
        self.default_vis = default_vasp_input_set

    def setup(self):
        input_files = set(["INCAR", "POSCAR", "POTCAR", "KPOINTS"])
        files = os.listdir(".")
        num_structures = 0
        if not set(files).issuperset(input_files):
            for f in files:
                if f.startswith("POSCAR") or f.startswith("CONTCAR"):
                    poscar = Poscar.from_file(f)
                    struct = poscar.struct
                    num_structures += 1
                elif f.lower().endswith(".cif"):
                    parser = CifParser(f)
                    struct = parser.get_structures()[0]
                    num_structures += 1
            if num_structures != 1:
                raise RuntimeError("{} structures found. Unable to continue.")
            else:
                self.default_vis.write_input(struct, ".")

    def run(self):
        with open(self.output_file, 'w') as f:
            subprocess.call(self.vasp_command, stdout=f)

    def postprocess(self):
        pass

    @property
    def name(self):
        return "Basic Vasp Job"


class SecondRelaxationVaspJob(BasicVaspJob):
    """
    Second relaxation vasp job.
    """

    OUTPUT_FILES = ['DOSCAR', 'INCAR', 'KPOINTS', 'POSCAR', 'PROCAR',
                    'vasprun.xml', 'CHGCAR', 'CHG', 'EIGENVAL', 'OSZICAR',
                    'WAVECAR', 'CONTCAR', 'IBZKPT', 'OUTCAR', 'vasp.out']

    def setup(self):
        for f in SecondRelaxationVaspJob.OUTPUT_FILES:
            if os.path.exists(f):
                shutil.copy(f, "{}.relax1".format(f))
        shutil.copy("CONTCAR", "POSCAR")
        incar = Incar.from_file("INCAR")
        incar['ISTART'] = 1
        incar.write_file("INCAR")

    def postprocess(self):
        for f in SecondRelaxationVaspJob.OUTPUT_FILES:
            if os.path.exists(f):
                shutil.copy(f, "{}.relax2".format(f))
        for f in os.listdir("."):
            if not f.endswith("gz"):
                with zopen(f, 'rb') as f_in, zopen('{}.gz'.format(f), 'wb') as f_out:
                    f_out.writelines(f_in)
                os.remove(f)

    @property
    def name(self):
        return "Second Relaxation Vasp Job"
