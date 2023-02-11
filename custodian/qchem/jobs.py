"""
This module implements basic kinds of jobs for QChem runs.
"""

import copy
import os
import shutil
import subprocess
import warnings

import numpy as np
from pymatgen.core import Molecule
from pymatgen.io.qchem.inputs import QCInput
from pymatgen.io.qchem.outputs import QCOutput, check_for_structure_changes
from pymatgen.io.qchem.sets import OptSet

from custodian.custodian import Job
from custodian.qchem.utils import perturb_coordinates, vector_list_diff

__author__ = "Samuel Blau, Brandon Wood, Shyam Dwaraknath, Evan Spotte-Smith"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/20/18"
__credits__ = "Xiaohui Qu"

try:
    from openbabel import openbabel as ob  # noqa: F401
except ImportError:
    raise RuntimeError("ERROR: Openbabel must be installed in order to use Q-Chem Custodian!")


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
        nboexe=None,
        save_scratch=False,
        backup=True,
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
            nboexe (str): Path to the NBO7 executable. Defaults to None.
            save_scratch (bool): Whether to save full scratch directory contents.
                Defaults to False.
            backup (bool): Whether to backup the initial input file. If True, the
                input will be copied with a ".orig" appended. Defaults to True.
        """
        try:
            self.qchem_command = qchem_command.split(" ")
        except AttributeError:
            if isinstance(qchem_command, list):
                for val in qchem_command:
                    if not isinstance(val, str):
                        raise ValueError("Must either pass a string or a list of strings")
            else:
                raise ValueError("Must either pass a string or a list of strings")
            self.qchem_command = qchem_command
        self.multimode = multimode
        self.input_file = input_file
        self.output_file = output_file
        self.max_cores = max_cores
        self.qclog_file = qclog_file
        self.suffix = suffix
        self.calc_loc = calc_loc
        self.nboexe = nboexe
        self.save_scratch = save_scratch
        self.backup = backup

        try:
            slurm_cores = int(os.environ["SLURM_CPUS_ON_NODE"])
            if slurm_cores < self.max_cores:
                self.max_cores = slurm_cores
                print("max_cores reduced from", max_cores, "to", self.max_cores)
            else:
                print("max_cores remain at", self.max_cores)
        except KeyError:
            print("SLURM_CPUS_ON_NODE not in environment")

    @property
    def current_command(self):
        """
        The command to run QChem
        """
        multi = {"openmp": "-nt", "mpi": "-np"}
        if self.multimode not in multi:
            raise RuntimeError("ERROR: Multimode should only be set to openmp or mpi")
        command = [multi[self.multimode], str(self.max_cores), self.input_file, self.output_file, "scratch"]
        command = self.qchem_command + command
        com_str = " ".join(command)
        return com_str

    def setup(self):
        """
        Sets up environment variables necessary to efficiently run QChem
        """
        if self.backup:
            shutil.copy(self.input_file, f"{self.input_file}.orig")
        if self.multimode == "openmp":
            os.environ["QCTHREADS"] = str(self.max_cores)
            os.environ["OMP_NUM_THREADS"] = str(self.max_cores)
        os.environ["QCSCRATCH"] = os.getcwd()
        if self.calc_loc is not None:
            os.environ["QCLOCALSCR"] = self.calc_loc
        qcinp = QCInput.from_file(self.input_file)
        if (
            qcinp.rem.get("run_nbo6", "none").lower() == "true"
            or qcinp.rem.get("nbo_external", "none").lower() == "true"
        ):
            os.environ["KMP_INIT_AT_FORK"] = "FALSE"
            if self.nboexe is None:
                raise RuntimeError("Trying to run NBO7 without providing NBOEXE in fworker! Exiting...")
            os.environ["NBOEXE"] = self.nboexe

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
            try:
                shutil.rmtree(scratch_dir)
            except FileNotFoundError:
                pass

    def run(self):
        """
        Perform the actual QChem run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        local_scratch = os.path.join(os.environ["QCLOCALSCR"], "scratch")
        if os.path.exists(local_scratch):
            shutil.rmtree(local_scratch)
        if os.path.exists(os.path.join(os.environ["QCSCRATCH"], "132.0")):
            os.mkdir(local_scratch)
            shutil.move(os.path.join(os.environ["QCSCRATCH"], "132.0"), local_scratch)
        with open(self.qclog_file, "w") as qclog:
            return subprocess.Popen(self.current_command, stdout=qclog, shell=True)  # pylint: disable=R1732

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
        transition_state=False,
        freq_before_opt=False,
        save_final_scratch=False,
        **QCJob_kwargs,
    ):
        """
        Optimize a structure and calculate vibrational frequencies to check if the
        structure is in a true minima.

        If there are an inappropriate number of imaginary frequencies (>0 for a
         minimum-energy structure, >1 for a transition-state), attempt to re-calculate
         using one of two methods:
            - Perturb the geometry based on the imaginary frequencies and re-optimize
            - Use the exact Hessian to inform a subsequent optimization
         After each geometry optimization, the frequencies are re-calculated to
         determine if a true minimum (or transition-state) has been found.

        Note: Very small imaginary frequencies (-15cm^-1 < nu < 0) are allowed
        if there is only one more than there should be. In other words, if there
        is one very small imaginary frequency, it is still treated as a minimum,
        and if there is one significant imaginary frequency and one very small
        imaginary frequency, it is still treated as a transition-state.

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
            linked (bool): Whether or not to use the linked flattener. If set to True (default),
                then the explicit Hessians from a vibrational frequency analysis will be used
                as the initial Hessian of subsequent optimizations. In many cases, this can
                significantly improve optimization efficiency.
            transition_state (bool): If True (default False), use a ts
                optimization (search for a saddle point instead of a minimum)
            freq_before_opt (bool): If True (default False), run a frequency
                calculation before any opt/ts searches to improve understanding
                of the local potential energy surface.
            save_final_scratch (bool): Whether to save full scratch directory contents
                at the end of the flattening. Defaults to False.
            **QCJob_kwargs: Passthrough kwargs to QCJob. See
                :class:`custodian.qchem.jobs.QCJob`.
        """
        if not os.path.exists(input_file):
            raise AssertionError("Input file must be present!")

        if transition_state:
            opt_method = "ts"
            perturb_index = 1
        else:
            opt_method = "opt"
            perturb_index = 0

        energy_diff_cutoff = 0.000001

        orig_input = QCInput.from_file(input_file)
        freq_rem = copy.deepcopy(orig_input.rem)
        freq_rem["job_type"] = "freq"
        opt_rem = copy.deepcopy(orig_input.rem)
        opt_rem["job_type"] = opt_method
        opt_geom_opt = None
        if "geom_opt2" in orig_input.rem.keys():
            freq_rem.pop("geom_opt2", None)
            if linked:
                opt_rem.pop("geom_opt2", None)
        first = True
        energy_history = []

        if freq_before_opt:
            if not linked:
                warnings.warn("WARNING: This first frequency calculation will not inform subsequent optimization!")
            yield (
                QCJob(
                    qchem_command=qchem_command,
                    multimode=multimode,
                    input_file=input_file,
                    output_file=output_file,
                    qclog_file=qclog_file,
                    suffix=".freq_pre",
                    save_scratch=True,
                    backup=first,
                    **QCJob_kwargs,
                )
            )

            freq_outdata = QCOutput(output_file + ".freq_pre").data
            if freq_outdata["version"] == "6":
                opt_set = OptSet(molecule=freq_outdata["initial_molecule"], qchem_version=freq_outdata["version"])
                opt_geom_opt = copy.deepcopy(opt_set.geom_opt)

            if linked:
                opt_rem["geom_opt_hessian"] = "read"
                if freq_outdata["version"] == "6":
                    opt_geom_opt["initial_hessian"] = "read"

            tmp_opt_rem = copy.deepcopy(opt_rem)
            if opt_rem["scf_algorithm"] == "diis":
                tmp_opt_rem["scf_guess_always"] = "True"
            opt_QCInput = QCInput(
                molecule=orig_input.molecule,
                rem=tmp_opt_rem,
                opt=orig_input.opt,
                pcm=orig_input.pcm,
                solvent=orig_input.solvent,
                smx=orig_input.smx,
                vdw_mode=orig_input.vdw_mode,
                van_der_waals=orig_input.van_der_waals,
                nbo=orig_input.nbo,
                geom_opt=opt_geom_opt,
            )
            opt_QCInput.write_file(input_file)
            first = False

        if linked:
            opt_rem["geom_opt_hessian"] = "read"

            for ii in range(max_iterations):
                yield (
                    QCJob(
                        qchem_command=qchem_command,
                        multimode=multimode,
                        input_file=input_file,
                        output_file=output_file,
                        qclog_file=qclog_file,
                        suffix=f".{opt_method}_" + str(ii),
                        save_scratch=True,
                        backup=first,
                        **QCJob_kwargs,
                    )
                )
                opt_outdata = QCOutput(output_file + f".{opt_method}_" + str(ii)).data
                opt_indata = QCInput.from_file(input_file + f".{opt_method}_" + str(ii))
                if opt_outdata["version"] == "6":
                    opt_geom_opt = copy.deepcopy(opt_indata.geom_opt)
                    opt_geom_opt["initial_hessian"] = "read"
                for key in opt_indata.rem:
                    if key not in ["job_type", "geom_opt2", "scf_guess_always"]:
                        if freq_rem.get(key, None) != opt_indata.rem[key]:
                            if "geom_opt" not in key:
                                freq_rem[key] = opt_indata.rem[key]
                        if opt_rem.get(key, None) != opt_indata.rem[key]:
                            opt_rem[key] = opt_indata.rem[key]
                first = False
                if opt_outdata["structure_change"] == "unconnected_fragments" and not opt_outdata["completion"]:
                    if not transition_state:
                        warnings.warn(
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
                    vdw_mode=orig_input.vdw_mode,
                    van_der_waals=orig_input.van_der_waals,
                    nbo=orig_input.nbo,
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
                        **QCJob_kwargs,
                    )
                )

                freq_outdata = QCOutput(output_file + ".freq_" + str(ii)).data
                freq_indata = QCInput.from_file(input_file + ".freq_" + str(ii))
                for key in freq_indata.rem:
                    if key not in ["job_type", "geom_opt2", "scf_guess_always"]:
                        if freq_rem.get(key, None) != freq_indata.rem[key]:
                            freq_rem[key] = freq_indata.rem[key]
                        if opt_rem.get(key, None) != freq_indata.rem[key]:
                            if key != "cpscf_nseg":
                                opt_rem[key] = freq_indata.rem[key]
                errors = freq_outdata.get("errors")

                if len(errors) != 0:
                    raise AssertionError("No errors should be encountered while flattening frequencies!")

                if not transition_state:
                    freq_list = freq_outdata.get("frequencies")

                    if len(freq_list) > 1:
                        freq_0 = freq_list[0]
                        freq_1 = freq_list[1]
                    else:
                        freq_0 = freq_outdata.get("frequencies")[0]
                        freq_1 = 100000.0
                        warnings.warn("Only single frequency. Two atom fragment")
                        break

                    if freq_0 > 0.0:
                        warnings.warn("All frequencies positive!")
                        break
                    if abs(freq_0) < 15.0 and freq_1 > 0.0:
                        warnings.warn("One negative frequency smaller than 15.0 - not worth further flattening!")
                        break
                    if len(energy_history) > 1:
                        if abs(energy_history[-1] - energy_history[-2]) < energy_diff_cutoff:
                            warnings.warn("Energy change below cutoff!")
                            break
                    tmp_opt_rem = copy.deepcopy(opt_rem)
                    if opt_rem["scf_algorithm"] == "diis":
                        tmp_opt_rem["scf_guess_always"] = "True"
                    opt_QCInput = QCInput(
                        molecule=opt_outdata.get("molecule_from_optimized_geometry"),
                        rem=tmp_opt_rem,
                        opt=orig_input.opt,
                        pcm=orig_input.pcm,
                        solvent=orig_input.solvent,
                        smx=orig_input.smx,
                        vdw_mode=orig_input.vdw_mode,
                        van_der_waals=orig_input.van_der_waals,
                        nbo=orig_input.nbo,
                        geom_opt=opt_geom_opt,
                    )
                    opt_QCInput.write_file(input_file)
                else:
                    freq_0 = freq_outdata.get("frequencies")[0]
                    freq_1 = freq_outdata.get("frequencies")[1]
                    freq_2 = freq_outdata.get("frequencies")[2]
                    if freq_0 < 0.0 < freq_1:
                        warnings.warn("Saddle point found!")
                        break
                    if abs(freq_1) < 15.0 and freq_2 > 0.0:
                        warnings.warn(
                            "Second small imaginary frequency (smaller than 15.0) - not worth further flattening!"
                        )
                        break
                    tmp_opt_rem = copy.deepcopy(opt_rem)
                    if opt_rem["scf_algorithm"] == "diis":
                        tmp_opt_rem["scf_guess_always"] = "True"
                    opt_QCInput = QCInput(
                        molecule=opt_outdata.get("molecule_from_optimized_geometry"),
                        rem=tmp_opt_rem,
                        opt=orig_input.opt,
                        pcm=orig_input.pcm,
                        solvent=orig_input.solvent,
                        smx=orig_input.smx,
                        vdw_mode=orig_input.vdw_mode,
                        van_der_waals=orig_input.van_der_waals,
                        nbo=orig_input.nbo,
                        # geom_opt=opt_geom_opt, # Will be uncommented once new optimizer supports TS calcs
                    )
                    opt_QCInput.write_file(input_file)
            if not save_final_scratch:
                shutil.rmtree(os.path.join(os.getcwd(), "scratch"))

        else:
            orig_opt_input = QCInput.from_file(input_file)
            history = []

            for ii in range(max_iterations):
                yield (
                    QCJob(
                        qchem_command=qchem_command,
                        multimode=multimode,
                        input_file=input_file,
                        output_file=output_file,
                        qclog_file=qclog_file,
                        suffix=f".{opt_method}_" + str(ii),
                        backup=first,
                        **QCJob_kwargs,
                    )
                )
                opt_outdata = QCOutput(output_file + f".{opt_method}_" + str(ii)).data
                if first:
                    orig_species = copy.deepcopy(opt_outdata.get("species"))
                    orig_charge = copy.deepcopy(opt_outdata.get("charge"))
                    orig_multiplicity = copy.deepcopy(opt_outdata.get("multiplicity"))
                    orig_energy = copy.deepcopy(opt_outdata.get("final_energy"))
                first = False
                if opt_outdata["structure_change"] == "unconnected_fragments" and not opt_outdata["completion"]:
                    if not transition_state:
                        warnings.warn(
                            "Unstable molecule broke into unconnected fragments which failed to optimize! Exiting..."
                        )
                        break
                freq_QCInput = QCInput(
                    molecule=opt_outdata.get("molecule_from_optimized_geometry"),
                    rem=freq_rem,
                    opt=orig_opt_input.opt,
                    pcm=orig_opt_input.pcm,
                    solvent=orig_opt_input.solvent,
                    smx=orig_opt_input.smx,
                    vdw_mode=orig_opt_input.vdw_mode,
                    van_der_waals=orig_opt_input.van_der_waals,
                    nbo=orig_input.nbo,
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
                        **QCJob_kwargs,
                    )
                )
                outdata = QCOutput(output_file + ".freq_" + str(ii)).data
                indata = QCInput.from_file(input_file + ".freq_" + str(ii))
                if "cpscf_nseg" in indata.rem:
                    freq_rem["cpscf_nseg"] = indata.rem["cpscf_nseg"]
                errors = outdata.get("errors")
                if len(errors) != 0:
                    raise AssertionError("No errors should be encountered while flattening frequencies!")
                if not transition_state:
                    freq_0 = outdata.get("frequencies")[0]
                    freq_1 = outdata.get("frequencies")[1]
                    if freq_0 > 0.0:
                        warnings.warn("All frequencies positive!")
                        if opt_outdata.get("final_energy") > orig_energy:
                            warnings.warn("WARNING: Energy increased during frequency flattening!")
                        break
                    if abs(freq_0) < 15.0 and freq_1 > 0.0:
                        warnings.warn("One negative frequency smaller than 15.0 - not worth further flattening!")
                        break
                    if len(energy_history) > 1:
                        if abs(energy_history[-1] - energy_history[-2]) < energy_diff_cutoff:
                            warnings.warn("Energy change below cutoff!")
                            break
                else:
                    freq_0 = outdata.get("frequencies")[0]
                    freq_1 = outdata.get("frequencies")[1]
                    freq_2 = outdata.get("frequencies")[2]
                    if freq_0 < 0.0 < freq_1:
                        warnings.warn("Saddle point found!")
                        break
                    if abs(freq_1) < 15.0 and freq_2 > 0.0:
                        warnings.warn(
                            "Second small imaginary frequency (smaller than 15.0) - not worth further flattening!"
                        )
                        break

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
                negative_freq_vecs = history[-1]["frequency_mode_vectors"][perturb_index]
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
                    if history[-1]["num_neg_freqs"] >= parent_hist["num_neg_freqs"]:
                        # check to see if the parent only has one child, aka only the positive perturbation has
                        # been tried,
                        # in which case just try the negative perturbation from the same parent
                        if len(parent_hist["children"]) == 1:
                            ref_mol = parent_hist["molecule"]
                            geom_to_perturb = parent_hist["geometry"]
                            negative_freq_vecs = parent_hist["frequency_mode_vectors"][perturb_index]
                            reversed_direction = True
                            standard = False
                            parent_hist["children"].append(len(history))
                        # If the parent has two children, aka both directions have been tried, then we have to
                        # get creative:
                        elif len(parent_hist["children"]) == 2:
                            # If we're dealing with just one negative frequency,
                            if parent_hist["num_neg_freqs"] == 1:
                                if history[parent_hist["children"][0]]["energy"] < history[-1]["energy"]:
                                    good_child = copy.deepcopy(history[parent_hist["children"][0]])
                                else:
                                    good_child = copy.deepcopy(history[-1])
                                if good_child["num_neg_freqs"] > 1:
                                    raise Exception(
                                        "ERROR: Child with lower energy has more negative frequencies! " "Exiting..."
                                    )
                                if good_child["energy"] < parent_hist["energy"]:
                                    make_good_child_next_parent = True
                                elif (
                                    vector_list_diff(
                                        good_child["frequency_mode_vectors"][perturb_index],
                                        parent_hist["frequency_mode_vectors"][perturb_index],
                                    )
                                    > 0.2
                                ):
                                    make_good_child_next_parent = True
                                else:
                                    raise Exception("ERROR: Good child not good enough! Exiting...")
                                if make_good_child_next_parent:
                                    good_child["index"] = len(history)
                                    history.append(good_child)
                                    ref_mol = history[-1]["molecule"]
                                    geom_to_perturb = history[-1]["geometry"]
                                    negative_freq_vecs = history[-1]["frequency_mode_vectors"][perturb_index]
                            else:
                                raise Exception("ERROR: Can't deal with multiple neg frequencies yet! Exiting...")
                        else:
                            raise AssertionError("ERROR: Parent cannot have more than two children! Exiting...")
                    # Implicitly, if the number of negative frequencies decreased from parent to child,
                    # continue normally.
                if standard:
                    history[-1]["children"].append(len(history))

                min_molecule_perturb_scale = 0.1
                scale_grid = 10
                perturb_scale_grid = (max_molecule_perturb_scale - min_molecule_perturb_scale) / scale_grid

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
                    if check_connectivity and not transition_state:
                        structure_successfully_perturbed = (
                            check_for_structure_changes(ref_mol, new_molecule) == "no_change"
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
                    rem=opt_rem,
                    opt=orig_opt_input.opt,
                    pcm=orig_opt_input.pcm,
                    solvent=orig_opt_input.solvent,
                    smx=orig_opt_input.smx,
                    vdw_mode=orig_opt_input.vdw_mode,
                    van_der_waals=orig_opt_input.van_der_waals,
                    nbo=orig_input.nbo,
                    geom_opt=orig_input.geom_opt,
                )
                new_opt_QCInput.write_file(input_file)
