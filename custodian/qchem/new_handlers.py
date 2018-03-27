# coding: utf-8

from __future__ import unicode_literals, division

import shutil
import time

"""
This module implements new error handlers for QChem runs. 
"""

import copy
import glob
import json
import logging
import os
import re
import tarfile
import numpy as np
from pymatgen.core.structure import Molecule
from pymatgen.io.qchem_io.inputs import QCInput
from pymatgen.io.qchem_io.outputs import QCOutput
from custodian.custodian import ErrorHandler
from custodian.utils import backup

__author__ = "Samuel Blau, Brandon Woods, Shyam Dwaraknath"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/26/18"


class QChemErrorHandler(ErrorHandler):
    """
    Master QChemErrorHandler class that handles a number of common errors
    that occur during QChem runs.
    """

    is_monitor = False

    def __init__(self, input_file="mol.qcin", output_file="mol.qcout", 
                 scf_max_cycles=200, geom_max_cycles=200, qchem_job=None):
        """
        Initializes the error handler from a set of input and output files.

        Args:
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            scf_max_cycles (int): The max iterations to set to fix SCF failure.
            geom_max_cycles (int): The max iterations to set to fix geometry
                optimization failure.
            qchem_job (QchemJob): the managing object to run qchem.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.scf_max_cycles = scf_max_cycles
        self.geom_max_cycles = geom_max_cycles
        self.qcinp = QCInput.from_file(self.input_file)
        self.outdata = None
        self.errors = None
        self.qchem_job = qchem_job

    def check(self):
        # Checks output file for errors.
        self.outdata = QCOutput(self.output_file).data
        self.errors = self.outdata.get("errors")
        return len(self.errors) > 0

    def correct(self):
        # backup({self.input_file, self.output_file})
        actions = []
                          
        if "SCF_failed_to_converge" in self.errors:
            # Check number of SCF cycles. If not set or less than scf_max_cycles, increase to that value and rerun. Otherwise, tell user to call SCF error handler and do nothing. 
            if self.qcinp.rem.get("max_scf_cycles") != self.scf_max_cycles:
                self.qcinp.rem["max_scf_cycles"] = self.scf_max_cycles
                actions.append({"dict": "rem",
                    "action": {"_set": {"max_scf_cycles": self.scf_max_cycles}}})
            else:
                print("Use SCF error handler")

        elif "out_of_opt_cycles" in self.errors:
            # Check number of opt cycles. If less than geom_max_cycles, increase to that value and rerun. Otherwise...?
            if self.qcinp.rem.get("geom_opt_max_cycles") != self.geom_max_cycles:
                self.qcinp.rem["geom_opt_max_cycles"] = self.geom_max_cycles
                actions.append({"dict": "rem",
                    "action": {"_set": {"geom_max_cycles:": self.scf_max_cycles}}})
            else:
                print("How do I get the geometry optimization converged when already at the maximum number of cycles?")

        elif "unable_to_determine_lamda" in self.errors:
            # Set last geom as now starting geom and rerun. If no opt cycles, use diff SCF strat? Diff initial guess? Change basis?
            # print(self.outdata.get("last_geometry"))
            if len(self.outdata.get("energy_trajectory")) > 1:
                self._set_new_coords(self.outdata.get("last_geometry")[0])
                actions.append({"dict": "molecule",
                    "action": {"_set": {"coords:": "last_geometry"}}})
            elif self.qcinp.rem.get("scf_algorithm") != "rca_diis":
                self.qcinp.rem["scf_algorithm"] = "rca_diis"
                actions.append({"dict": "rem",
                    "action": {"_set": {"scf_algorithm": "rca_diis"}}})
            else:
                print("Use a different initial guess? Perhaps a different basis?")

        elif "linear_dependent_basis" in self.errors:
            # DIIS -> RCA_DIIS. If already RCA_DIIS, change basis?
            if self.qcinp.rem.get("scf_algorithm") != "rca_diis":
                self.qcinp.rem["scf_algorithm"] = "rca_diis"
                actions.append({"dict": "rem",
                    "action": {"_set": {"scf_algorithm": "rca_diis"}}})
            else:
                print("Perhaps use a better basis?")

        elif "failed_to_transform_coords" in self.errors:
            # Check for symmetry flag in rem. If not False, set to False and rerun. If already False, increase threshold?
            if not self.qcinp.rem.get("sym_ignore") or self.qcinp.rem.get("symmetry"):
                self.qcinp.rem["sym_ignore"] = True
                self.qcinp.rem["symmetry"] = False
                actions.append({"dict": "rem",
                    "action": {"_set": {"sym_ignore": True}}})
                actions.append({"dict": "rem",
                    "action": {"_set": {"symmetry": False}}})
            else:
                print("Perhaps increase the threshold?")

        elif "input_file_error" in self.errors:
            print("Something is wrong with the input file. Examine error message by hand.") 
            return {"errors": self.errors, "actions": None}

        elif "failed_to_read_input" in self.errors:
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is. 
            return {"errors": self.errors, "actions": "rerun job as-is"}

        elif "IO_error" in self.errors:
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is. 
            return {"errors": self.errors, "actions": "rerun job as-is"}

        elif "unknown_error" in self.errors:
            print("Examine error message by hand.") 
            return {"errors": self.errors, "actions": None}

        else:
            # You should never get here. If correct is being called then errors should have at least one entry,
            # in which case it should have been caught by the if/elifs above. 
            Print("If you get this message, something has gone terribly wrong!")
            return {"errors": self.errors, "actions": None}

        self.qcinp.write_file(self.input_file)

        return {"errors": self.errors, "actions": actions}

    def _set_new_coords(self, coords):
        formatted_coords = []
        for ii in range(len(coords)):
            temp_coords = []
            for jj in range(3):
                temp_coords += [float(coords[ii][jj+1])]
            formatted_coords += [temp_coords]
        self.qcinp.molecule = Molecule(species=self.qcinp.molecule.species, coords=formatted_coords, charge=self.qcinp.molecule.charge, spin_multiplicity=self.qcinp.molecule.spin_multiplicity)






class QChemSCFErrorHandler(ErrorHandler):
    """
    QChem ErrorHandler class that addresses SCF non-convergence.
    """

    is_monitor = False

    def __init__(self, input_file="mol.qcin", output_file="mol.qcout", 
                 rca_gdm_thresh=1.0E-3, scf_max_cycles=200, qchem_job=None):
        """
        Initializes the error handler from a set of input and output files.

        Args:
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            rca_gdm_thresh (float): The threshold for the prior scf algorithm.
                If last deltaE is larger than the threshold try RCA_DIIS
                first, else, try DIIS_GDM first.
            scf_max_cycles (int): The max iterations to set to fix SCF failure.
            qchem_job (QchemJob): the managing object to run qchem.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.scf_max_cycles = scf_max_cycles
        self.geom_max_cycles = geom_max_cycles
        self.qcinp = QCInput.from_file(self.input_file)
        self.outdata = None
        self.errors = None
        self.qchem_job = qchem_job

    def check(self):
        # Checks output file for errors.
        self.outdata = QCOutput(self.output_file).data
        self.errors = self.outdata.get("errors")
        return len(self.errors) > 0

    def correct(self):
        backup({self.input_file, self.output_file})
        actions = []


















    # def fix_scf(self):
    #     comments = self.fix_step.params.get("comment", "")
    #     scf_pattern = re.compile(r"<SCF Fix Strategy>(.*)</SCF Fix "
    #                              r"Strategy>", flags=re.DOTALL)
    #     old_strategy_text = re.findall(scf_pattern, comments)

    #     if len(old_strategy_text) > 0:
    #         old_strategy_text = old_strategy_text[0]
    #     od = self.outdata[self.error_step_id]

    #     if "Negative Eigen" in self.errors:
    #         if "thresh" not in self.fix_step.params["rem"]:
    #             self.fix_step.set_integral_threshold(thresh=12)
    #             return "use tight integral threshold"
    #         elif int(self.fix_step.params["rem"]["thresh"]) < 14:
    #             self.fix_step.set_integral_threshold(thresh=14)
    #             return "use even tighter integral threshold"

    #     if len(od["scf_iteration_energies"]) == 0 \
    #             or len(od["scf_iteration_energies"][-1]) <= 10:
    #         if 'Exit Code 134' in self.errors:
    #             # immature termination of SCF
    #             return self.fix_error_code_134()
    #         else:
    #             return None

    #     if od["jobtype"] in ["opt", "ts", "aimd"] \
    #             and len(od["molecules"]) >= 2:
    #         strategy = "reset"
    #     elif len(old_strategy_text) > 0:
    #         strategy = json.loads(old_strategy_text)
    #         strategy["current_method_id"] += 1
    #     else:
    #         strategy = dict()
    #         scf_iters = od["scf_iteration_energies"][-1]
    #         if scf_iters[-1][1] >= self.rca_gdm_thresh:
    #             strategy["methods"] = ["increase_iter", "rca_diis", "gwh",
    #                                    "gdm", "rca", "core+rca", "fon"]
    #             strategy["current_method_id"] = 0
    #         else:
    #             strategy["methods"] = ["increase_iter", "diis_gdm", "gwh",
    #                                    "rca", "gdm", "core+gdm", "fon"]
    #             strategy["current_method_id"] = 0
    #         strategy["version"] = 2.0

    #     # noinspection PyTypeChecker
    #     if strategy == "reset":
    #         self.fix_step.set_scf_algorithm_and_iterations(
    #             algorithm="diis", iterations=self.scf_max_cycles)
    #         if self.error_step_id > 0:
    #             self.set_scf_initial_guess("read")
    #         else:
    #             self.set_scf_initial_guess("sad")
    #         if od["jobtype"] in ["opt", "ts"]:
    #             self.set_last_input_geom(od["molecules"][-1])
    #         else:
    #             assert od["jobtype"] == "aimd"
    #             from pymatgen.io.qchem import QcNucVeloc
    #             from pymatgen.io.xyz import XYZ
    #             scr_dir = od["scratch_dir"]
    #             qcnv_filepath = os.path.join(scr_dir, "AIMD", "NucVeloc")
    #             qc_md_view_filepath = os.path.join(scr_dir, "AIMD", "View.xyz")
    #             qcnv = QcNucVeloc(qcnv_filepath)
    #             qc_md_view = XYZ.from_file(qc_md_view_filepath)
    #             assert len(qcnv.velocities) == len(qc_md_view.all_molecules)
    #             aimd_steps = self.fix_step.params["rem"]["aimd_steps"]
    #             elapsed_steps = len(qc_md_view.all_molecules)
    #             remaining_steps = aimd_steps - elapsed_steps + 1
    #             self.fix_step.params["rem"]["aimd_steps"] = remaining_steps
    #             self.set_last_input_geom(qc_md_view.molecule)
    #             self.fix_step.set_velocities(qcnv.velocities[-1])
    #             self.fix_step.params["rem"].pop("aimd_init_veloc", None)
    #             traj_num = max([0] + [int(f.split(".")[1])
    #                                    for f in glob.glob("traj_View.*.xyz")])
    #             dest_view_filename = "traj_View.{}.xyz".format(traj_num + 1)
    #             dest_nv_filename = "traj_NucVeloc.{}.txt".format(traj_num + 1)
    #             logging.info("Backing up trajectory files to {} and {}."
    #                          .format(dest_view_filename, dest_nv_filename))
    #             shutil.copy(qc_md_view_filepath, dest_view_filename)
    #             shutil.copy(qcnv_filepath, dest_nv_filename)
    #         if len(old_strategy_text) > 0:
    #             comments = scf_pattern.sub("", comments)
    #             self.fix_step.params["comment"] = comments
    #             if len(comments.strip()) == 0:
    #                 self.fix_step.params.pop("comment")
    #         return "reset"
    #     elif strategy["current_method_id"] > len(strategy["methods"])-1:
    #         return None
    #     else:
    #         # noinspection PyTypeChecker
    #         method = strategy["methods"][strategy["current_method_id"]]
    #         if method == "increase_iter":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="diis", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("sad")
    #         elif method == "rca_diis":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="rca_diis", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("sad")
    #         elif method == "gwh":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="diis", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("gwh")
    #         elif method == "gdm":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="gdm", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("sad")
    #         elif method == "rca":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="rca", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("sad")
    #         elif method == "core+rca":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="rca", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("core")
    #         elif method == "diis_gdm":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="diis_gdm", iterations=self.scf_max_cycles)
    #             self.fix_step.set_scf_initial_guess("sad")
    #         elif method == "core+gdm":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="gdm", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("core")
    #         elif method == "fon":
    #             self.fix_step.set_scf_algorithm_and_iterations(
    #                 algorithm="diis", iterations=self.scf_max_cycles)
    #             self.set_scf_initial_guess("sad")
    #             natoms = len(od["molecules"][-1])
    #             self.fix_step.params["rem"]["occupations"] = 2
    #             self.fix_step.params["rem"]["fon_norb"] = int(natoms * 0.618)
    #             self.fix_step.params["rem"]["fon_t_start"] = 300
    #             self.fix_step.params["rem"]["fon_t_end"] = 300
    #             self.fix_step.params["rem"]["fon_e_thresh"] = 6
    #             self.fix_step.set_integral_threshold(14)
    #             self.fix_step.set_scf_convergence_threshold(7)
    #         else:
    #             raise ValueError("fix method " + method + " is not supported")
    #         strategy_text = "<SCF Fix Strategy>"
    #         strategy_text += json.dumps(strategy, indent=4, sort_keys=True)
    #         strategy_text += "</SCF Fix Strategy>"
    #         if len(old_strategy_text) > 0:
    #             comments = scf_pattern.sub(strategy_text, comments)
    #         else:
    #             comments += "\n" + strategy_text
    #         self.fix_step.params["comment"] = comments
    #         return method

    # def set_last_input_geom(self, new_mol):
    #     for i in range(self.error_step_id, -1, -1):
    #         qctask = self.qcinp.jobs[i]
    #         if isinstance(qctask.mol, Molecule):
    #             qctask.mol = copy.deepcopy(new_mol)

    # def set_scf_initial_guess(self, guess="sad"):
    #     if "scf_guess" not in self.fix_step.params["rem"] \
    #             or self.error_step_id > 0 \
    #             or self.fix_step.params["rem"]["scf_guess"] != "read":
    #         self.fix_step.set_scf_initial_guess(guess)

    # def fix_geom_opt(self):
    #     comments = self.fix_step.params.get("comment", "")
    #     geom_pattern = re.compile(r"<Geom Opt Fix Strategy>(.*)"
    #                               r"</Geom Opt Fix Strategy>",
    #                               flags=re.DOTALL)
    #     old_strategy_text = re.findall(geom_pattern, comments)

    #     if len(old_strategy_text) > 0:
    #         old_strategy_text = old_strategy_text[0]

    #     od = self.outdata[self.error_step_id]

    #     if 'Lamda Determination Failed' in self.errors and len(od["molecules"])>=2:
    #         self.fix_step.set_scf_algorithm_and_iterations(
    #             algorithm="diis", iterations=self.scf_max_cycles)
    #         if self.error_step_id > 0:
    #             self.set_scf_initial_guess("read")
    #         else:
    #             self.set_scf_initial_guess("sad")
    #         self.set_last_input_geom(od["molecules"][-1])
    #         if od["jobtype"] == "aimd":
    #             aimd_steps = self.fix_step.params["rem"]["aimd_steps"]
    #             elapsed_steps = len(od["molecules"]) - 1
    #             remaining_steps = aimd_steps - elapsed_steps + 1
    #             self.fix_step.params["rem"]["aimd_steps"] = remaining_steps
    #         if len(old_strategy_text) > 0:
    #             comments = geom_pattern.sub("", comments)
    #             self.fix_step.params["comment"] = comments
    #             if len(comments.strip()) == 0:
    #                 self.fix_step.params.pop("comment")
    #         return "reset"

    #     if len(od["molecules"]) <= 10:
    #         # immature termination of geometry optimization
    #         if 'Exit Code 134' in self.errors:
    #             return self.fix_error_code_134()
    #         else:
    #             return None
    #     if len(old_strategy_text) > 0:
    #         strategy = json.loads(old_strategy_text)
    #         strategy["current_method_id"] += 1
    #     else:
    #         strategy = dict()
    #         strategy["methods"] = ["increase_iter", "GDIIS", "CartCoords"]
    #         strategy["current_method_id"] = 0
    #     if strategy["current_method_id"] > len(strategy["methods"]) - 1:
    #         return None
    #     else:
    #         method = strategy["methods"][strategy["current_method_id"]]
    #         if method == "increase_iter":
    #             self.fix_step.set_geom_max_iterations(self.geom_max_cycles)
    #             self.set_last_input_geom(od["molecules"][-1])
    #         elif method == "GDIIS":
    #             self.fix_step.set_geom_opt_use_gdiis(subspace_size=5)
    #             self.fix_step.set_geom_max_iterations(self.geom_max_cycles)
    #             self.set_last_input_geom(od["molecules"][-1])
    #         elif method == "CartCoords":
    #             self.fix_step.set_geom_opt_coords_type("cartesian")
    #             self.fix_step.set_geom_max_iterations(self.geom_max_cycles)
    #             self.fix_step.set_geom_opt_use_gdiis(0)
    #             self.set_last_input_geom(od["molecules"][-1])
    #         else:
    #             raise ValueError("fix method" + method + "is not supported")
    #         strategy_text = "<Geom Opt Fix Strategy>"
    #         strategy_text += json.dumps(strategy, indent=4, sort_keys=True)
    #         strategy_text += "</Geom Opt Fix Strategy>"
    #         if len(old_strategy_text) > 0:
    #             comments = geom_pattern.sub(strategy_text, comments)
    #         else:
    #             comments += "\n" + strategy_text
    #         self.fix_step.params["comment"] = comments
    #         return method

