# coding: utf-8

from __future__ import unicode_literals, division
import math

# New QChem job module


import os
import shutil
import copy
import subprocess
import numpy as np
from pymatgen.core import Molecule
from pymatgen.io.qchem.inputs import QCInput
from pymatgen.io.qchem.outputs import QCOutput
from custodian.custodian import Job
from pymatgen.analysis.molecule_structure_comparator import MoleculeStructureComparator

__author__ = "Samuel Blau, Brandon Wood, Shyam Dwaraknath"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/20/18"
__credits__ = "Xiaohui Qu"


class QCJob(Job):
    """
    A basic QChem Job.
    """

    def __init__(self,
                 qchem_command,
                 multimode="openmp",
                 input_file="mol.qin",
                 output_file="mol.qout",
                 max_cores=32,
                 qclog_file="mol.qclog",
                 suffix="",
                 scratch_dir="/dev/shm/qcscratch/",
                 save_scratch=False,
                 save_name="default_save_name",
                 backup=True):
        """
        Args:
            qchem_command (str): Command to run QChem.
            multimode (str): Parallelization scheme, either openmp or mpi.
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            max_cores (int): Maximum number of cores to parallelize over.
                Defaults to 32.
            qclog_file (str): Name of the file to redirect the standard output
                to. None means not to record the standard output.
            suffix (str): String to append to the file in postprocess.
            scratch_dir (str): QCSCRATCH directory. Defaults to "/dev/shm/qcscratch/".
            save_scratch (bool): Whether to save scratch directory contents.
                Defaults to False.
            save_name (str): Name of the saved scratch directory. Defaults to
                to "default_save_name".
            backup (bool): Whether to backup the initial input file. If True, the
                input will be copied with a ".orig" appended. Defaults to True.
        """
        self.qchem_command = qchem_command.split(" ")
        self.multimode = multimode
        self.input_file = input_file
        self.output_file = output_file
        self.max_cores = max_cores
        self.qclog_file = qclog_file
        self.suffix = suffix
        self.scratch_dir = scratch_dir
        self.save_scratch = save_scratch
        self.save_name = save_name
        self.backup = backup

    @property
    def current_command(self):
        multimode_index = 0
        if self.save_scratch:
            command = [
                "-save", "",
                str(self.max_cores), self.input_file, self.output_file,
                self.save_name
            ]
            multimode_index = 1
        else:
            command = [
                "", str(self.max_cores), self.input_file, self.output_file
            ]
        if self.multimode == 'openmp':
            command[multimode_index] = "-nt"
        elif self.multimode == 'mpi':
            command[multimode_index] = "-np"
        else:
            print("ERROR: Multimode should only be set to openmp or mpi")
        command = self.qchem_command + command
        return command

    def setup(self):
        if self.backup:
            shutil.copy(self.input_file, "{}.orig".format(self.input_file))
        os.putenv("QCSCRATCH", self.scratch_dir)
        if self.multimode == 'openmp':
            os.putenv('QCTHREADS', str(self.max_cores))
            os.putenv('OMP_NUM_THREADS', str(self.max_cores))

    def postprocess(self):
        if self.save_scratch:
            shutil.copytree(
                os.path.join(self.scratch_dir, self.save_name),
                os.path.join(os.path.dirname(self.input_file), self.save_name))
        if self.suffix != "":
            shutil.move(self.input_file, self.input_file + self.suffix)
            shutil.move(self.output_file, self.output_file + self.suffix)
            shutil.move(self.qclog_file, self.qclog_file + self.suffix)

    def run(self):
        """
        Perform the actual QChem run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        qclog = open(self.qclog_file, 'w')
        p = subprocess.Popen(self.current_command, stdout=qclog)
        return p

    @classmethod
    def opt_with_frequency_flattener(cls,
                                     qchem_command,
                                     multimode="openmp",
                                     input_file="mol.qin",
                                     output_file="mol.qout",
                                     qclog_file="mol.qclog",
                                     max_iterations=10,
                                     max_molecule_perturb_scale=0.3,
                                     reversed_direction=False,
                                     ignore_connectivity=False,
                                     **QCJob_kwargs):
        """
        Optimize a structure and calculate vibrational frequencies to check if the
        structure is in a true minima. If a frequency is negative, iteratively
        perturbe the geometry, optimize, and recalculate frequencies until all are
        positive, aka a true minima has been found.

        Args:
            qchem_command (str): Command to run QChem.
            multimode (str): Parallelization scheme, either openmp or mpi.
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            max_iterations (int): Number of perturbation -> optimization -> frequency
                iterations to perform. Defaults to 10.
            max_molecule_perturb_scale (float): The maximum scaled perturbation that
                can be applied to the molecule. Defaults to 0.3.
            reversed_direction (bool): Whether to reverse the direction of the
                vibrational frequency vectors. Defaults to False.
            ignore_connectivity (bool): Whether to ignore differences in connectivity
                introduced by structural perturbation. Defaults to False.
            **QCJob_kwargs: Passthrough kwargs to QCJob. See
                :class:`custodian.qchem.jobs.QCJob`.
        """

        min_molecule_perturb_scale = 0.1
        scale_grid = 10
        perturb_scale_grid = (
            max_molecule_perturb_scale - min_molecule_perturb_scale
        ) / scale_grid
        msc = MoleculeStructureComparator()

        if not os.path.exists(input_file):
            raise AssertionError('Input file must be present!')
        orig_opt_input = QCInput.from_file(input_file)
        orig_opt_rem = copy.deepcopy(orig_opt_input.rem)
        orig_freq_rem = copy.deepcopy(orig_opt_input.rem)
        orig_freq_rem["job_type"] = "freq"
        first = True

        for ii in range(max_iterations):
            yield (QCJob(
                qchem_command=qchem_command,
                multimode=multimode,
                input_file=input_file,
                output_file=output_file,
                qclog_file=qclog_file,
                suffix=".opt_" + str(ii),
                backup=first,
                **QCJob_kwargs))
            first = False
            opt_outdata = QCOutput(output_file + ".opt_" + str(ii)).data
            if opt_outdata["structure_change"] == "unconnected_fragments":
                print("Unstable molecule broke into unconnected fragments! Exiting...")
                break
            else:
                freq_QCInput = QCInput(
                    molecule=opt_outdata.get("molecule_from_optimized_geometry"),
                    rem=orig_freq_rem,
                    opt=orig_opt_input.opt,
                    pcm=orig_opt_input.pcm,
                    solvent=orig_opt_input.solvent)
                freq_QCInput.write_file(input_file)
                yield (QCJob(
                    qchem_command=qchem_command,
                    multimode=multimode,
                    input_file=input_file,
                    output_file=output_file,
                    qclog_file=qclog_file,
                    suffix=".freq_" + str(ii),
                    backup=first,
                    **QCJob_kwargs))
                outdata = QCOutput(output_file + ".freq_" + str(ii)).data
                errors = outdata.get("errors")
                if len(errors) != 0:
                    raise AssertionError('No errors should be encountered while flattening frequencies!')
                if outdata.get('frequencies')[0] > 0.0:
                    print("All frequencies positive!")
                    break
                else:
                    negative_freq_vecs = outdata.get("frequency_mode_vectors")[0]
                    old_coords = outdata.get("initial_geometry")
                    old_molecule = outdata.get("initial_molecule")
                    structure_successfully_perturbed = False

                    for molecule_perturb_scale in np.arange(
                            max_molecule_perturb_scale, min_molecule_perturb_scale,
                            -perturb_scale_grid):
                        new_coords = perturb_coordinates(
                            old_coords=old_coords,
                            negative_freq_vecs=negative_freq_vecs,
                            molecule_perturb_scale=molecule_perturb_scale,
                            reversed_direction=reversed_direction)
                        new_molecule = Molecule(
                            species=outdata.get('species'),
                            coords=new_coords,
                            charge=outdata.get('charge'),
                            spin_multiplicity=outdata.get('multiplicity'))
                        if msc.are_equal(old_molecule, new_molecule) or ignore_connectivity:
                            structure_successfully_perturbed = True
                            break
                    if not structure_successfully_perturbed:
                        raise Exception(
                            "Unable to perturb coordinates to remove negative frequency without changing the bonding structure"
                        )

                    new_opt_QCInput = QCInput(
                        molecule=new_molecule,
                        rem=orig_opt_rem,
                        opt=orig_opt_input.opt,
                        pcm=orig_opt_input.pcm,
                        solvent=orig_opt_input.solvent)
                    new_opt_QCInput.write_file(input_file)


def perturb_coordinates(old_coords, negative_freq_vecs, molecule_perturb_scale,
                        reversed_direction):
    max_dis = max(
        [math.sqrt(sum([x**2 for x in vec])) for vec in negative_freq_vecs])
    scale = molecule_perturb_scale / max_dis
    normalized_vecs = [[x * scale for x in vec] for vec in negative_freq_vecs]
    direction = 1.0
    if reversed_direction:
        direction = -1.0
    return [[c + v * direction for c, v in zip(coord, vec)]
            for coord, vec in zip(old_coords, normalized_vecs)]
