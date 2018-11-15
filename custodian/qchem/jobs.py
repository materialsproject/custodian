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
from pymatgen.analysis.graphs import MoleculeGraph
from pymatgen.analysis.local_env import OpenBabelNN
from custodian.custodian import Job


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
                 max_cores,
                 multimode="openmp",
                 input_file="mol.qin",
                 output_file="mol.qout",
                 qclog_file="mol.qclog",
                 suffix="",
                 scratch_dir="/dev/shm/qcscratch/",
                 save_scratch=False,
                 read_scratch=False,
                 save_name="default_save_name",
                 backup=True):
        """
        Args:
            qchem_command (str): Command to run QChem.
            max_cores (int): Maximum number of cores to parallelize over.
            multimode (str): Parallelization scheme, either openmp or mpi.
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            qclog_file (str): Name of the file to redirect the standard output
                to. None means not to record the standard output.
            suffix (str): String to append to the file in postprocess.
            scratch_dir (str): QCSCRATCH directory. Defaults to "/dev/shm/qcscratch/".
            save_scratch (bool): Whether to save scratch directory contents.
                Defaults to False.
            read_scratch (bool): Whether to read saved scratch directory contents.
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
        self.read_scratch = read_scratch
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
        elif self.read_scratch:
            command = [
                "", str(self.max_cores), self.input_file, self.output_file,
                self.save_name
            ]
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
                                     check_connectivity=True,
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
            check_connectivity (bool): Whether to check differences in connectivity
                introduced by structural perturbation. Defaults to True.
            **QCJob_kwargs: Passthrough kwargs to QCJob. See
                :class:`custodian.qchem.jobs.QCJob`.
        """

        if not os.path.exists(input_file):
            raise AssertionError('Input file must be present!')
        orig_opt_input = QCInput.from_file(input_file)
        orig_opt_rem = copy.deepcopy(orig_opt_input.rem)
        orig_freq_rem = copy.deepcopy(orig_opt_input.rem)
        orig_freq_rem["job_type"] = "freq"
        first = True
        history = []

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
            opt_outdata = QCOutput(output_file + ".opt_" + str(ii)).data
            if first:
                orig_species = copy.deepcopy(opt_outdata.get('species'))
                orig_charge = copy.deepcopy(opt_outdata.get('charge'))
                orig_multiplicity = copy.deepcopy(opt_outdata.get('multiplicity'))
                orig_energy = copy.deepcopy(opt_outdata.get('final_energy'))
            first = False
            if opt_outdata["structure_change"] == "unconnected_fragments" and not opt_outdata["completion"]:
                print("Unstable molecule broke into unconnected fragments which failed to optimize! Exiting...")
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
                    if opt_outdata.get('final_energy') > orig_energy:
                        print("WARNING: Energy increased during frequency flattening!")
                    break
                else:
                    hist = {}
                    hist["molecule"] = copy.deepcopy(outdata.get("initial_molecule"))
                    hist["geometry"] = copy.deepcopy(outdata.get("initial_geometry"))
                    hist["frequencies"] = copy.deepcopy(outdata.get("frequencies"))
                    hist["frequency_mode_vectors"] = copy.deepcopy(outdata.get("frequency_mode_vectors"))
                    hist["num_neg_freqs"] = sum(1 for freq in outdata.get("frequencies") if freq < 0)
                    hist["energy"] = copy.deepcopy(opt_outdata.get("final_energy"))
                    hist["index"] = len(history)
                    hist["children"] = []
                    history.append(hist)

                    ref_mol = history[-1]["molecule"]
                    geom_to_perturb = history[-1]["geometry"]
                    negative_freq_vecs = history[-1]["frequency_mode_vectors"][0]
                    reversed_direction = False
                    standard = True

                    # If we've found one or more negative frequencies in two consecutive iterations, let's dig in deeper:
                    if len(history) > 1:
                        # Start by finding the latest iteration's parent:
                        if history[-1]["index"] in history[-2]["children"]:
                            parent_hist = history[-2]
                            history[-1]["parent"] = parent_hist["index"]
                        elif history[-1]["index"] in history[-3]["children"]:
                            parent_hist = history[-3]
                            history[-1]["parent"] = parent_hist["index"]
                        else:
                            raise AssertionError("ERROR: your parent should always be one or two iterations behind you! Exiting...")

                        # if the number of negative frequencies has remained constant or increased from parent to child,
                        if history[-1]["num_neg_freqs"] >= parent_hist["num_neg_freqs"]:
                            # check to see if the parent only has one child, aka only the positive perturbation has been tried,
                            # in which case just try the negative perturbation from the same parent
                            if len(parent_hist["children"]) == 1:
                                ref_mol = parent_hist["molecule"]
                                geom_to_perturb = parent_hist["geometry"]
                                negative_freq_vecs = parent_hist["frequency_mode_vectors"][0]
                                reversed_direction = True
                                standard = False
                                parent_hist["children"].append(len(history))
                            # If the parent has two children, aka both directions have been tried, then we have to get creative:
                            elif len(parent_hist["children"]) == 2:
                                # If we're dealing with just one negative frequency, 
                                if parent_hist["num_neg_freqs"] == 1:
                                    make_good_child_next_parent = False
                                    if history[parent_hist["children"][0]]["energy"] < history[-1]["energy"]:
                                        good_child = copy.deepcopy(history[parent_hist["children"][0]])
                                    else:
                                        good_child = copy.deepcopy(history[-1])
                                    if good_child["num_neg_freqs"] > 1:
                                        raise Exception("ERROR: Child with lower energy has more negative frequencies! Exiting...")
                                    elif good_child["energy"] < parent_hist["energy"]:
                                        make_good_child_next_parent = True
                                    elif vector_list_diff(good_child["frequency_mode_vectors"][0],parent_hist["frequency_mode_vectors"][0]) > 0.2:
                                        make_good_child_next_parent = True
                                    else:
                                        raise Exception("ERROR: Good child not good enough! Exiting...")
                                    if make_good_child_next_parent:
                                        good_child["index"] = len(history)
                                        history.append(good_child)
                                        ref_mol = history[-1]["molecule"]
                                        geom_to_perturb = history[-1]["geometry"]
                                        negative_freq_vecs = history[-1]["frequency_mode_vectors"][0]
                                else:
                                    raise Exception("ERROR: Can't deal with multiple neg frequencies yet! Exiting...")
                            else:
                                raise AssertionError("ERROR: Parent cannot have more than two childen! Exiting...")
                        # Implicitly, if the number of negative frequencies decreased from parent to child, continue normally.
                    if standard:
                        history[-1]["children"].append(len(history))

                    min_molecule_perturb_scale = 0.1
                    scale_grid = 10
                    perturb_scale_grid = (
                        max_molecule_perturb_scale - min_molecule_perturb_scale
                    ) / scale_grid

                    structure_successfully_perturbed = False
                    for molecule_perturb_scale in np.arange(
                            max_molecule_perturb_scale, min_molecule_perturb_scale,
                            -perturb_scale_grid):
                        new_coords = perturb_coordinates(
                            old_coords=geom_to_perturb,
                            negative_freq_vecs=negative_freq_vecs,
                            molecule_perturb_scale=molecule_perturb_scale,
                            reversed_direction=reversed_direction)
                        new_molecule = Molecule(
                            species=orig_species,
                            coords=new_coords,
                            charge=orig_charge,
                            spin_multiplicity=orig_multiplicity)
                        if check_connectivity:
                            old_molgraph = MoleculeGraph.with_local_env_strategy(ref_mol,
                                                               OpenBabelNN(),
                                                               reorder=False,
                                                               extend_structure=False)
                            new_molgraph = MoleculeGraph.with_local_env_strategy(new_molecule,
                                                               OpenBabelNN(),
                                                               reorder=False,
                                                               extend_structure=False)
                            if old_molgraph.isomorphic_to(new_molgraph):
                                structure_successfully_perturbed = True
                                break
                    if not structure_successfully_perturbed:
                        raise Exception(
                            "ERROR: Unable to perturb coordinates to remove negative frequency without changing the connectivity! Exiting..."
                        )

                    new_opt_QCInput = QCInput(
                        molecule=new_molecule,
                        rem=orig_opt_rem,
                        opt=orig_opt_input.opt,
                        pcm=orig_opt_input.pcm,
                        solvent=orig_opt_input.solvent)
                    new_opt_QCInput.write_file(input_file)

    @classmethod
    def chained_freq_opt(cls,
                         qchem_command,
                         multimode="openmp",
                         input_file="mol.qin",
                         output_file="mol.qout",
                         qclog_file="mol.qclog",
                         max_iterations=10,
                         **QCJob_kwargs):

        if not os.path.exists(input_file):
            raise AssertionError('Input file must be present!')
        orig_freq_input = QCInput.from_file(input_file)
        orig_freq_rem = copy.deepcopy(orig_freq_input.rem)
        orig_opt_rem = copy.deepcopy(orig_freq_input.rem)
        orig_opt_rem["job_type"] = "opt"
        orig_opt_rem["SCF_GUESS"] = "read"
        orig_opt_rem["GEOM_OPT_HESSIAN"] = "read"
        first = True

        for ii in range(max_iterations):
            yield (QCJob(
                qchem_command=qchem_command,
                multimode=multimode,
                input_file=input_file,
                output_file=output_file,
                qclog_file=qclog_file,
                suffix=".freq_" + str(ii),
                scratch_dir=os.getcwd(),
                save_scratch=True,
                save_name="freq_scratch",
                backup=first,
                **QCJob_kwargs))
            freq_outdata = QCOutput(output_file + ".freq_" + str(ii)).data
            first = False
            opt_QCInput = QCInput(
                molecule="read",
                rem=orig_opt_rem,
                opt=orig_freq_input.opt,
                pcm=orig_freq_input.pcm,
                solvent=orig_freq_input.solvent)
            opt_QCInput.write_file(input_file)
            yield (QCJob(
                qchem_command=qchem_command,
                multimode=multimode,
                input_file=input_file,
                output_file=output_file,
                qclog_file=qclog_file,
                suffix=".freq_" + str(ii),
                scratch_dir=os.getcwd(),
                read_scratch=True,
                save_name="freq_scratch",
                backup=first,
                **QCJob_kwargs))
            opt_outdata = QCOutput(output_file + ".opt_" + str(ii)).data
            errors = opt_outdata.get("errors")
            break


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

def vector_list_diff(vecs1, vecs2):
    diff = 0.0
    if len(vecs1) != len(vecs2):
        raise AssertionError("ERROR: Vectors must be of equal length! Exiting...")
    for ii, vec1 in enumerate(vecs1):
        diff += np.linalg.norm(vecs2[ii] - vec1)
    return diff
