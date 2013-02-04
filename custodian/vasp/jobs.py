#!/usr/bin/env python

"""
TODO: Change the module doc.
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

from custodian.jobs import Job


class BasicVaspJob(Job):
    """
    Very basic vasp job. Just runs whatever is in the directory. But
    conceivably can be a complex processing of inputs etc. with initialization.
    """

    def __init__(self, default_vasp_input_set=MITVaspInputSet()):
        self.default_vis = default_vasp_input_set

    def setup(self):
        files = os.listdir(".")
        num_structures = 0
        if not set(files).issuperset(set(["INCAR", "POSCAR", "POTCAR", "KPOINTS"])):
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
        args = ["mpirun", "/share/apps/bin/pvasp.5.2.11"]
        output = subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]
        with open("vasp.out", 'w') as f:
            f.write(output)

    def postprocess(self):
        pass

    @property
    def name(self):
        return "Basic Vasp Job"


class SecondRelaxationVaspJob(BasicVaspJob):
    """
    Very basic vasp job. Just runs whatever is in the directory. But
    conceivably can be a complex processing of inputs etc. with initialization.
    """

    OUTPUT_FILES = ['DOSCAR', 'INCAR', 'KPOINTS', 'POSCAR', 'PROCAR',
                    'vasprun.xml', 'CHGCAR', 'CHG', 'EIGENVAL', 'OSZICAR',
                    'WAVECAR', 'CONTCAR', 'IBZKPT', 'OUTCAR', 'vasp.out']

    def setup(self):
        for f in SecondRelaxationVaspJob.OUTPUT_FILES:
            shutil.copy(f, "{}.relax1".format(f))
        shutil.copy("CONTCAR", "POSCAR")
        incar = Incar.from_file("INCAR")
        incar['ISTART'] = 1
        incar.write_file("INCAR")

    def postprocess(self):
        for f in SecondRelaxationVaspJob.OUTPUT_FILES:
            shutil.copy(f, "{}.relax2".format(f))
        for f in os.listdir("."):
            if not f.endswith("gz"):
                with zopen(f, 'rb') as f_in, zopen('{}.gz'.format(f), 'wb') as f_out:
                    f_out.writelines(f_in)
                os.remove(f)

    @property
    def name(self):
        return "Second relaxation Vasp Job"

