# coding: utf-8

"""
This module implements basic kinds of jobs for QChem runs.
"""

import math
import os
import shutil
import copy
import subprocess
import numpy as np
from pymatgen.core import Molecule
from pymatgen.io.qchem.inputs import QCInput
from pymatgen.io.qchem.outputs import QCOutput, check_for_structure_changes
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

    def __init__(
        self,
        qchem_command,
        max_cores,
        multimode="openmp",
        input_file="mol.qin",
        output_file="mol.qout",
        qclog_file="mol.qclog",
        suffix="",
        calc_loc=None,
        save_scratch=False,
        backup=True
    ):
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
            calc_loc (str): Path where Q-Chem should run. Defaults to None, in
                which case Q-Chem will run in the system-defined QCLOCALSCR.
            save_scratch (bool): Whether to save full scratch directory contents.
                Defaults to False.
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
        self.calc_loc = calc_loc
        self.save_scratch = save_scratch
        self.backup = backup

    @property
    def current_command(self):
        """
        The command to run QChem
        """
        multi = {"openmp": "-nt", "mpi": "-np"}
        if self.multimode not in multi:
            raise RuntimeError("ERROR: Multimode should only be set to openmp or mpi")
        command = [
            multi[self.multimode],
            str(self.max_cores),
            self.input_file,
            self.output_file,
            "scratch"
        ]
        command = self.qchem_command + command
        com_str = ""
        for part in command:
            com_str = com_str + " " + part
        return com_str

    def setup(self):
        """
        Sets up environment variables necessary to efficiently run QChem
        """
        if self.backup:
            shutil.copy(self.input_file, "{}.orig".format(self.input_file))
        if self.multimode == 'openmp':
            os.environ['QCTHREADS'] = str(self.max_cores)
            os.environ['OMP_NUM_THREADS'] = str(self.max_cores)
        os.environ["QCSCRATCH"] = os.getcwd()
        if self.calc_loc is not None:
            os.environ["QCLOCALSCR"] = self.calc_loc

    def postprocess(self):
        """
        Renames and removes scratch files after running QChem
        """
        scratch_dir = os.path.join(os.environ["QCSCRATCH"], "scratch")
        for file in ["HESS", "GRAD", "plots/dens.0.cube"]:
            file_path = os.path.join(scratch_dir, file)
            if os.path.exists(file_path):
                shutil.copy(file_path, os.getcwd())
        if self.suffix != "":
            shutil.move(self.input_file, self.input_file + self.suffix)
            shutil.move(self.output_file, self.output_file + self.suffix)
            shutil.move(self.qclog_file, self.qclog_file + self.suffix)
            for file in ["HESS", "GRAD", "dens.0.cube"]:
                if os.path.exists(file):
                    shutil.move(file, file + self.suffix)
        if not self.save_scratch:
            shutil.rmtree(scratch_dir)

    def run(self):
        """
        Perform the actual QChem run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        local_scratch = os.path.join(os.environ["QCLOCALSCR"], "scratch")
        if os.path.exists(local_scratch):
            shutil.rmtree(local_scratch)
        qclog = open(self.qclog_file, 'w')
        p = subprocess.Popen(self.current_command, stdout=qclog, shell=True)
        return p

    @classmethod
    def opt_with_frequency_flattener(
        cls,
        qchem_command,
        multimode="openmp",
        input_file="mol.qin",
        output_file="mol.qout",
        qclog_file="mol.qclog",
        max_iterations=10,
        max_molecule_perturb_scale=0.3,
        check_connectivity=True,
        linked=True,
        save_final_scratch=False,
        **QCJob_kwargs
    ):
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
            linked (bool): Whether or not to use the linked flattener. Defaults to True.
            save_final_scratch (bool): Whether to save full scratch directory contents
                at the end of the flattening. Defaults to False.
            **QCJob_kwargs: Passthrough kwargs to QCJob. See
                :class:`custodian.qchem.jobs.QCJob`.
        """
        if not os.path.exists(input_file):
            raise AssertionError("Input file must be present!")

        if linked:

            energy_diff_cutoff = 0.0000001

            orig_input = QCInput.from_file(input_file)
            freq_rem = copy.deepcopy(orig_input.rem)
            freq_rem["job_type"] = "freq"
            opt_rem = copy.deepcopy(orig_input.rem)
            opt_rem["geom_opt_hessian"] = "read"
            opt_rem["scf_guess_always"] = True
            first = True
            energy_history = []

            for ii in range(max_iterations):
                yield (
                    QCJob(
                        qchem_command=qchem_command,
                        multimode=multimode,
                        input_file=input_file,
                        output_file=output_file,
                        qclog_file=qclog_file,
                        suffix=".opt_" + str(ii),
                        save_scratch=True,
                        backup=first,
                        **QCJob_kwargs
                    )
                )
                opt_outdata = QCOutput(output_file + ".opt_" + str(ii)).data
                opt_indata = QCInput.from_file(input_file + ".opt_" + str(ii))
                if opt_indata.rem["scf_algorithm"] != freq_rem["scf_algorithm"]:
                    freq_rem["scf_algorithm"] = opt_indata.rem["scf_algorithm"]
                    opt_rem["scf_algorithm"] = opt_indata.rem["scf_algorithm"]
                first = False
                if (
                    opt_outdata["structure_change"] == "unconnected_fragments"
                    and not opt_outdata["completion"]
                ):
                    print(
                        "Unstable molecule broke into unconnected fragments which failed to optimize! Exiting..."
                    )
                    break
                energy_history.append(opt_outdata.get("final_energy"))
                freq_QCInput = QCInput(
                    molecule=opt_outdata.get("molecule_from_optimized_geometry"),
                    rem=freq_rem,
                    opt=orig_input.opt,
                    pcm=orig_input.pcm,
                    solvent=orig_input.solvent,
                    smx=orig_input.smx,
                )
                freq_QCInput.write_file(input_file)
                yield (
                    QCJob(
                        qchem_command=qchem_command,
                        multimode=multimode,
                        input_file=input_file,
                        output_file=output_file,
                        qclog_file=qclog_file,
                        suffix=".freq_" + str(ii),
                        save_scratch=True,
                        backup=first,
                        **QCJob_kwargs
                    )
                )
                outdata = QCOutput(output_file + ".freq_" + str(ii)).data
                indata = QCInput.from_file(input_file + ".freq_" + str(ii))
                if indata.rem["scf_algorithm"] != freq_rem["scf_algorithm"]:
                    freq_rem["scf_algorithm"] = indata.rem["scf_algorithm"]
                    opt_rem["scf_algorithm"] = indata.rem["scf_algorithm"]
                errors = outdata.get("errors")
                if len(errors) != 0:
                    raise AssertionError(
                        "No errors should be encountered while flattening frequencies!"
                    )
                if outdata.get("frequencies")[0] > 0.0:
                    print("All frequencies positive!")
                    break
                if (
                    abs(outdata.get("frequencies")[0]) < 15.0
                    and outdata.get("frequencies")[1] > 0.0
                ):
                    print(
                        "One negative frequency smaller than 15.0 - not worth further flattening!"
                    )
                    break
                if len(energy_history) > 1:
                    if (
                        abs(energy_history[-1] - energy_history[-2])
                        < energy_diff_cutoff
                    ):
                        print("Energy change below cutoff!")
                        break
                opt_QCInput = QCInput(
                    molecule=opt_outdata.get(
                        "molecule_from_optimized_geometry"
                    ),
                    rem=opt_rem,
                    opt=orig_input.opt,
                    pcm=orig_input.pcm,
                    solvent=orig_input.solvent,
                    smx=orig_input.smx,
                )
                opt_QCInput.write_file(input_file)
            if not save_final_scratch:
                shutil.rmtree(os.path.join(os.getcwd(), "scratch"))

        else:
            if not os.path.exists(input_file):
                raise AssertionError("Input file must be present!")
            orig_opt_input = QCInput.from_file(input_file)
            orig_opt_rem = copy.deepcopy(orig_opt_input.rem)
            orig_freq_rem = copy.deepcopy(orig_opt_input.rem)
            orig_freq_rem["job_type"] = "freq"
            first = True
            history = []

            for ii in range(max_iterations):
                yield (
                    QCJob(
                        qchem_command=qchem_command,
                        multimode=multimode,
                        input_file=input_file,
                        output_file=output_file,
                        qclog_file=qclog_file,
                        suffix=".opt_" + str(ii),
                        backup=first,
                        **QCJob_kwargs
                    )
                )
                opt_outdata = QCOutput(output_file + ".opt_" + str(ii)).data
                if first:
                    orig_species = copy.deepcopy(opt_outdata.get("species"))
                    orig_charge = copy.deepcopy(opt_outdata.get("charge"))
                    orig_multiplicity = copy.deepcopy(opt_outdata.get("multiplicity"))
                    orig_energy = copy.deepcopy(opt_outdata.get("final_energy"))
                first = False
                if (
                    opt_outdata["structure_change"] == "unconnected_fragments"
                    and not opt_outdata["completion"]
                ):
                    print(
                        "Unstable molecule broke into unconnected fragments which failed to optimize! Exiting..."
                    )
                    break
                freq_QCInput = QCInput(
                    molecule=opt_outdata.get("molecule_from_optimized_geometry"),
                    rem=orig_freq_rem,
                    opt=orig_opt_input.opt,
                    pcm=orig_opt_input.pcm,
                    solvent=orig_opt_input.solvent,
                    smx=orig_opt_input.smx,
                )
                freq_QCInput.write_file(input_file)
                yield (
                    QCJob(
                        qchem_command=qchem_command,
                        multimode=multimode,
                        input_file=input_file,
                        output_file=output_file,
                        qclog_file=qclog_file,
                        suffix=".freq_" + str(ii),
                        backup=first,
                        **QCJob_kwargs
                    )
                )
                outdata = QCOutput(output_file + ".freq_" + str(ii)).data
                errors = outdata.get("errors")
                if len(errors) != 0:
                    raise AssertionError(
                        "No errors should be encountered while flattening frequencies!"
                    )
                if outdata.get("frequencies")[0] > 0.0:
                    print("All frequencies positive!")
                    if opt_outdata.get("final_energy") > orig_energy:
                        print(
                            "WARNING: Energy increased during frequency flattening!"
                        )
                    break
                hist = {}
                hist["molecule"] = copy.deepcopy(
                    outdata.get("initial_molecule")
                )
                hist["geometry"] = copy.deepcopy(
                    outdata.get("initial_geometry")
                )
                hist["frequencies"] = copy.deepcopy(outdata.get("frequencies"))
                hist["frequency_mode_vectors"] = copy.deepcopy(
                    outdata.get("frequency_mode_vectors")
                )
                hist["num_neg_freqs"] = sum(
                    1 for freq in outdata.get("frequencies") if freq < 0
                )
                hist["energy"] = copy.deepcopy(opt_outdata.get("final_energy"))
                hist["index"] = len(history)
                hist["children"] = []
                history.append(hist)

                ref_mol = history[-1]["molecule"]
                geom_to_perturb = history[-1]["geometry"]
                negative_freq_vecs = history[-1]["frequency_mode_vectors"][0]
                reversed_direction = False
                standard = True

                # If we've found one or more negative frequencies in two consecutive iterations, let's dig in
                # deeper:
                if len(history) > 1:
                    # Start by finding the latest iteration's parent:
                    if history[-1]["index"] in history[-2]["children"]:
                        parent_hist = history[-2]
                        history[-1]["parent"] = parent_hist["index"]
                    elif history[-1]["index"] in history[-3]["children"]:
                        parent_hist = history[-3]
                        history[-1]["parent"] = parent_hist["index"]
                    else:
                        raise AssertionError(
                            "ERROR: your parent should always be one or two iterations behind you! Exiting..."
                        )

                    # if the number of negative frequencies has remained constant or increased from parent to
                    # child,
                    if (
                        history[-1]["num_neg_freqs"]
                        >= parent_hist["num_neg_freqs"]
                    ):
                        # check to see if the parent only has one child, aka only the positive perturbation has
                        # been tried,
                        # in which case just try the negative perturbation from the same parent
                        if len(parent_hist["children"]) == 1:
                            ref_mol = parent_hist["molecule"]
                            geom_to_perturb = parent_hist["geometry"]
                            negative_freq_vecs = parent_hist[
                                "frequency_mode_vectors"
                            ][0]
                            reversed_direction = True
                            standard = False
                            parent_hist["children"].append(len(history))
                        # If the parent has two children, aka both directions have been tried, then we have to
                        # get creative:
                        elif len(parent_hist["children"]) == 2:
                            # If we're dealing with just one negative frequency,
                            if parent_hist["num_neg_freqs"] == 1:
                                make_good_child_next_parent = False
                                if (
                                    history[parent_hist["children"][0]][
                                        "energy"
                                    ]
                                    < history[-1]["energy"]
                                ):
                                    good_child = copy.deepcopy(
                                        history[parent_hist["children"][0]]
                                    )
                                else:
                                    good_child = copy.deepcopy(history[-1])
                                if good_child["num_neg_freqs"] > 1:
                                    raise Exception(
                                        "ERROR: Child with lower energy has more negative frequencies! "
                                        "Exiting..."
                                    )
                                if (
                                    good_child["energy"] < parent_hist["energy"]
                                ):
                                    make_good_child_next_parent = True
                                elif (
                                    vector_list_diff(
                                        good_child["frequency_mode_vectors"][0],
                                        parent_hist["frequency_mode_vectors"][
                                            0
                                        ],
                                    )
                                    > 0.2
                                ):
                                    make_good_child_next_parent = True
                                else:
                                    raise Exception(
                                        "ERROR: Good child not good enough! Exiting..."
                                    )
                                if make_good_child_next_parent:
                                    good_child["index"] = len(history)
                                    history.append(good_child)
                                    ref_mol = history[-1]["molecule"]
                                    geom_to_perturb = history[-1]["geometry"]
                                    negative_freq_vecs = history[-1][
                                        "frequency_mode_vectors"
                                    ][0]
                            else:
                                raise Exception(
                                    "ERROR: Can't deal with multiple neg frequencies yet! Exiting..."
                                )
                        else:
                            raise AssertionError(
                                "ERROR: Parent cannot have more than two childen! Exiting..."
                            )
                    # Implicitly, if the number of negative frequencies decreased from parent to child,
                    # continue normally.
                if standard:
                    history[-1]["children"].append(len(history))

                min_molecule_perturb_scale = 0.1
                scale_grid = 10
                perturb_scale_grid = (
                    max_molecule_perturb_scale - min_molecule_perturb_scale
                ) / scale_grid

                structure_successfully_perturbed = False
                for molecule_perturb_scale in np.arange(
                    max_molecule_perturb_scale,
                    min_molecule_perturb_scale,
                    -perturb_scale_grid,
                ):
                    new_coords = perturb_coordinates(
                        old_coords=geom_to_perturb,
                        negative_freq_vecs=negative_freq_vecs,
                        molecule_perturb_scale=molecule_perturb_scale,
                        reversed_direction=reversed_direction,
                    )
                    new_molecule = Molecule(
                        species=orig_species,
                        coords=new_coords,
                        charge=orig_charge,
                        spin_multiplicity=orig_multiplicity,
                    )
                    if check_connectivity:
                        structure_successfully_perturbed = (
                            check_for_structure_changes(ref_mol, new_molecule)
                            == "no_change"
                        )
                        if structure_successfully_perturbed:
                            break
                if not structure_successfully_perturbed:
                    raise Exception(
                        "ERROR: Unable to perturb coordinates to remove negative frequency without changing "
                        "the connectivity! Exiting..."
                    )

                new_opt_QCInput = QCInput(
                    molecule=new_molecule,
                    rem=orig_opt_rem,
                    opt=orig_opt_input.opt,
                    pcm=orig_opt_input.pcm,
                    solvent=orig_opt_input.solvent,
                    smx=orig_opt_input.smx,
                )
                new_opt_QCInput.write_file(input_file)


def perturb_coordinates(
    old_coords, negative_freq_vecs, molecule_perturb_scale, reversed_direction
):
    """
    Perturbs a structure along the imaginary mode vibrational frequency vectors
    """
    max_dis = max([math.sqrt(sum([x ** 2 for x in vec])) for vec in negative_freq_vecs])
    scale = molecule_perturb_scale / max_dis
    normalized_vecs = [[x * scale for x in vec] for vec in negative_freq_vecs]
    direction = 1.0
    if reversed_direction:
        direction = -1.0
    return [
        [c + v * direction for c, v in zip(coord, vec)]
        for coord, vec in zip(old_coords, normalized_vecs)
    ]


def vector_list_diff(vecs1, vecs2):
    """
    Calculates the summed difference of two vectors
    """
    diff = 0.0
    if len(vecs1) != len(vecs2):
        raise AssertionError("ERROR: Vectors must be of equal length! Exiting...")
    for ii, vec1 in enumerate(vecs1):
        diff += np.linalg.norm(vecs2[ii] - vec1)
    return diff
