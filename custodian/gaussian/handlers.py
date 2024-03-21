# coding: utf-8

"""
This module implements error handlers for Gaussian runs.
"""

import os
import re
import math
import glob
import shutil
import logging
import datetime

import numpy as np
import matplotlib.pyplot as plt

from matplotlib.ticker import MaxNLocator

from monty.io import zopen

from pymatgen.io.gaussian import GaussianInput, GaussianOutput

from custodian.utils import backup
from custodian.custodian import ErrorHandler

__author__ = "Rasha Atwi"
__version__ = "0.1"
__maintainer__ = "Rasha Atwi"
__email__ = "rasha.atwi@stonybrook.edu"
__status__ = "Alpha"
__date__ = "5/13/21"

BACKUP_FILES = {
    "checkpoint": "*.[Cc][Hh][Kk]",
    "form_checkpoint": "*.[Ff][Cc][Hh][Kk]",
    "rwf": "*.[Rr][Ww][Ff]",
    "inp": "*.[Ii][Nn][Pp]",
    "int": "*.[Ii][Nn][Tt]",
    "d2e": "*.[Dd]2[Ee]",
    "skr": "*.[Ss][Kk][Rr]",
    "convergence": "convergence.png",
}


def backup_gaussian_files(filenames, prefix):
    all_files = {}
    for k, v in BACKUP_FILES.items():
        files = glob.glob(v)
        if files:
            all_files[k] = files
            for file in files:
                filenames.append(file)
    backup(filenames, prefix)
    return all_files


class GaussianErrorHandler(ErrorHandler):
    # definition of job errors as they appear in Gaussian output file
    error_defs = {'Optimization stopped': 'opt_steps',
                  'Convergence failure': 'scf_convergence',
                  'FormBX had a problem': 'linear_bend',
                  'Linear angle in Tors.': 'linear_bend',
                  'Inv3 failed in PCMMkU': 'solute_solvent_surface',
                  'Error in internal coordinate system': 'internal_coords',
                  'End of file in ZSymb': 'zmatrix',
                  'There are no atoms in this input structure !': 'missing_mol',
                  'Atom specifications unexpectedly found in input stream.': 'found_coords',
                  'End of file reading connectivity.': 'coords',
                  'FileIO operation on non-existent file.': 'missing_file',
                  'No data on chk file.': 'empty_file',
                  'Bad file opened by FileIO': 'bad_file',
                  'Z-matrix optimization but no Z-matrix variables.': 'coord_inputs',
                  'A syntax error was detected in the input line.': 'syntax',
                  'The combination of multiplicity ([0-9]+) and \s+? ([0-9]+) '
                  'electrons is impossible.': 'charge',
                  'Out-of-memory error in routine': 'insufficient_mem'}

    error_patt = re.compile("|".join(list(error_defs)))
    recom_mem_patt = re.compile(
        r"Use %mem=([0-9]+)MW to provide the minimum "
        r"amount of memory required to complete this "
        r"step."
    )
    conv_critera = {
        "max_force": re.compile(r"\s+(Maximum Force)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"),
        "rms_force": re.compile(r"\s+(RMS {5}Force)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"),
        "max_disp": re.compile(
            r"\s+(Maximum Displacement)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"
        ),
        "rms_disp": re.compile(
            r"\s+(RMS {5}Displacement)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"
        ),
    }

    grid_patt = re.compile(r"(-?\d{5})")
    GRID_NAMES = [
        "finegrid",
        "fine",
        "superfinegrid",
        "superfine",
        "coarsegrid",
        "coarse",
        "sg1grid",
        "sg1",
        "pass0grid",
        "pass0",
    ]
    MEM_UNITS = ["kb", "mb", "gb", "tb", "kw", "mw", "gw", "tw"]

    activate_better_guess = False

    def __init__(
        self,
        input_file,
        output_file,
        stderr_file="stderr.txt",
        cart_coords=True,
        scf_max_cycles=100,
        opt_max_cycles=100,
        job_type="normal",
        lower_functional=None,
        lower_basis_set=None,
        prefix="error",
        check_convergence=True,
    ):
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.cart_coords = cart_coords
        self.errors = set()
        self.gout = None
        self.gin = None
        self.scf_max_cycles = scf_max_cycles
        self.opt_max_cycles = opt_max_cycles
        self.job_type = job_type
        self.lower_functional = lower_functional
        self.lower_basis_set = lower_basis_set
        self.prefix = prefix
        self.check_convergence = check_convergence
        self.conv_data = None
        self.recom_mem = None
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)

    @staticmethod
    def _recursive_lowercase(obj):
        if isinstance(obj, dict):
            updated_obj = {}
            for k, v in obj.items():
                updated_obj[k.lower()] = GaussianErrorHandler._recursive_lowercase(v)
            return updated_obj
        elif isinstance(obj, str):
            return obj.lower()
        elif hasattr(obj, "__iter__"):
            updated_obj = []
            for i in obj:
                updated_obj.append(GaussianErrorHandler._recursive_lowercase(i))
            return updated_obj
        else:
            return obj

    @staticmethod
    def _recursive_remove_space(obj):
        updated_obj = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                updated_obj[key.strip()] = GaussianErrorHandler._recursive_remove_space(
                    value
                )
            elif isinstance(value, str):
                updated_obj[key.strip()] = value.strip()
            else:
                updated_obj[key.strip()] = value
        return updated_obj

    @staticmethod
    def _update_route_params(route_params, key, value):
        obj = route_params.get(key, {})
        if not obj:
            route_params[key] = value
        elif isinstance(obj, str):
            update = (
                {key: {obj: None, **value}}
                if isinstance(value, dict)
                else {key: {obj: None, value: None}}
            )
            route_params.update(update)
        elif isinstance(obj, dict):
            update = value if isinstance(value, dict) else {value: None}
            route_params[key].update(update)
        return route_params

    @staticmethod
    def _int_keyword(route_params):
        if "int" in route_params:
            int_key = "int"
        elif "integral" in route_params:
            int_key = "integral"
        else:
            int_key = ""
        # int_key = 'int' if 'int' in route_params else 'integral'
        return int_key, route_params.get(int_key, "")

    @staticmethod
    def _int_grid(route_params):
        _, int_value = GaussianErrorHandler._int_keyword(route_params)
        options = ["ultrafine", "ultrafinegrid", "99590"]

        if isinstance(int_value, str) and int_value in options:
            return True
        elif isinstance(int_value, dict):
            if int_value.get("grid") in options:
                return True
            if set(int_value) & set(options):
                return True
        return False

    @staticmethod
    def convert_mem(mem, unit):
        # convert dynamic mem to Mb
        conversion = {
            "kb": 1 / 1000,
            "mb": 1,
            "gb": 1000,
            "tb": 1000**2,
            "": 7.63e-6,
            "kw": 7.63e-3,
            "mw": 7.63,
            "gw": 7.63e3,
            "tw": 7.63e6,
        }
        return mem * conversion[unit]

    @staticmethod
    def _find_dynamic_memory_allocated(link0_params):
        mem_key = None
        for k in link0_params:
            if k.lower() == "%mem":
                mem_key = k
                break
        dynamic_mem = link0_params.get(mem_key)
        if dynamic_mem:
            # default memory unit in Gaussian is words
            dynamic_mem = dynamic_mem.lower()
            mem_unit = ""
            for unit in GaussianErrorHandler.MEM_UNITS:
                if unit in dynamic_mem:
                    mem_unit = unit
                    break
            dynamic_mem = float(dynamic_mem.strip(mem_unit))
            dynamic_mem = GaussianErrorHandler.convert_mem(dynamic_mem, mem_unit)
        return mem_key, dynamic_mem

    def _add_int(self):
        if not GaussianErrorHandler._int_grid(self.gin.route_parameters):
            # nothing int is set or is set to different values
            warning_msg = (
                "Changing the numerical integration grid. "
                "This will bring changes in the predicted "
                "total energy. It is necessary to use the same "
                "integration grid in all the calculations in "
                "the same study in order for the computed "
                "energies and molecular properties to be "
                "comparable."
            )

            int_key, int_value = GaussianErrorHandler._int_keyword(
                self.gin.route_parameters
            )
            if not int_value and GaussianErrorHandler._not_g16(self.gout):
                # if int keyword is missing and Gaussian version is 03 or
                # 09, set integration grid to ultrafine
                int_key = int_key or "int"
                self.logger.warning(warning_msg)
                self.gin.route_parameters[int_key] = "ultrafine"
                return True
            elif isinstance(int_value, dict):
                # if int grid is set and is different from ultrafine,
                # set it to ultrafine (works when others int options are
                # specified)
                flag = True if "grid" in self.gin.route_parameters[int_key] else False
                for key in self.gin.route_parameters[int_key]:
                    if key in self.GRID_NAMES or self.grid_patt.match(key):
                        self.gin.route_parameters[int_key].pop(key)
                        flag = True
                        break
                if flag or GaussianErrorHandler._not_g16(self.gout):
                    self.logger.warning(warning_msg)
                    self.gin.route_parameters[int_key]["grid"] = "ultrafine"
                    return True
            else:
                if int_value in self.GRID_NAMES or self.grid_patt.match(int_value):
                    # if int grid is set and is different from ultrafine,
                    # set it to ultrafine (works when no other int options
                    # are specified)
                    self.logger.warning(warning_msg)
                    self.gin.route_parameters[int_key] = "ultrafine"
                    return True
                elif GaussianErrorHandler._not_g16(self.gout):
                    # if int grid is not specified, and Gaussian version is
                    # not 16, update with ultrafine integral grid
                    self.logger.warning(warning_msg)
                    GaussianErrorHandler._update_route_params(
                        self.gin.route_parameters, int_key, {"grid": "ultrafine"}
                    )
                    return True
        else:
            return False
        return False

    @staticmethod
    def _not_g16(gout):
        return "16" not in gout.version

    @staticmethod
    def _monitor_convergence(data, directory="./"):
        fig, ax = plt.subplots(ncols=2, nrows=2, figsize=(12, 10))
        for i, (k, v) in enumerate(data["values"].items()):
            row = int(np.floor(i / 2))
            col = i % 2
            iters = range(0, len(v))
            ax[row, col].plot(iters, v, color="#cf3759", linewidth=2)
            ax[row, col].axhline(
                y=data["thresh"][k], linewidth=2, color="black", linestyle="--"
            )
            ax[row, col].tick_params(which="major", length=8)
            ax[row, col].tick_params(
                axis="both", which="both", direction="in", labelsize=16
            )
            ax[row, col].set_xlabel("Iteration", fontsize=16)
            ax[row, col].set_ylabel("{}".format(k), fontsize=16)
            ax[row, col].xaxis.set_major_locator(MaxNLocator(integer=True))
            ax[row, col].grid(ls="--", zorder=1)
        plt.tight_layout()
        plt.savefig(os.path.join(directory, "convergence.png"))

    def check(self, directory="./"):
        # TODO: this backups the original file instead of the actual one
        if "linear_bend" in self.errors:
            os.rename(
                os.path.join(directory, self.input_file + ".prev"),
                os.path.join(directory, self.input_file),
            )

        self.gin = GaussianInput.from_file(os.path.join(directory, self.input_file))
        self.gin.route_parameters = GaussianErrorHandler._recursive_lowercase(
            self.gin.route_parameters
        )
        self.gin.route_parameters = GaussianErrorHandler._recursive_remove_space(
            self.gin.route_parameters
        )
        self.gout = GaussianOutput(os.path.join(directory, self.output_file))
        self.errors = set()
        error_patts = set()
        # TODO: move this to pymatgen?
        self.conv_data = {"values": {}, "thresh": {}}
        with zopen(os.path.join(directory, self.output_file)) as f:
            for line in f:
                error_match = GaussianErrorHandler.error_patt.search(line)
                mem_match = GaussianErrorHandler.recom_mem_patt.search(line)
                if error_match:
                    patt = error_match.group(0)
                    error_patts.add(patt)
                    self.errors.add(GaussianErrorHandler.error_defs[patt])
                if mem_match:
                    mem = mem_match.group(1)
                    self.recom_mem = GaussianErrorHandler.convert_mem(float(mem), "mw")

                if self.check_convergence and "opt" in self.gin.route_parameters:
                    for k, v in GaussianErrorHandler.conv_critera.items():
                        if v.search(line):
                            m = v.search(line)
                            if k not in self.conv_data["values"]:
                                self.conv_data["values"][k] = [m.group(2)]
                                self.conv_data["thresh"][k] = float(m.group(3))
                            else:
                                self.conv_data["values"][k].append(m.group(2))

        # TODO: it only plots after the job finishes, modify?
        if self.conv_data["values"] and all(
            len(v) >= 2 for v in self.conv_data["values"].values()
        ):
            for k, v in self.conv_data["values"].items():
                # convert strings to float taking into account the
                # possibility of having ******** values
                self.conv_data["values"][k] = np.genfromtxt(np.array(v))
            GaussianErrorHandler._monitor_convergence(self.conv_data)
        for patt in error_patts:
            self.logger.error(patt)
        return len(self.errors) > 0

    def correct(self, directory="./"):
        actions = []
        # to avoid situations like 'linear_bend', where if we backup input_file,
        # it will not be the actual input used in the current calc
        # shutil.copy(self.input_file, f'{self.input_file}.backup')
        # backup_files = [self.input_file, self.output_file,
        #                 self.stderr_file]
        # checkpoint = glob.glob('*.[Cc][Hh][Kk]')
        # form_checkpoint = glob.glob('*.[Ff][Cc][Hh][Kk]')
        # png = glob.glob('convergence.png')
        # [backup_files.append(i[0]) for i in [checkpoint, form_checkpoint, png]
        #  if i]
        # backup(backup_files, self.prefix)
        # os.remove(f'{self.input_file}.backup')
        backup_files = [self.input_file, self.output_file, self.stderr_file] + list(
            BACKUP_FILES.values()
        )
        backup(backup_files, prefix=self.prefix, directory=directory)
        # backup_gaussian_files(backup_files, prefix=self.prefix)
        if "scf_convergence" in self.errors:
            self.gin.route_parameters = GaussianErrorHandler._update_route_params(
                self.gin.route_parameters, "scf", {}
            )
            # if the SCF procedure has failed to converge
            if self.gin.route_parameters.get("scf").get("maxcycle") != str(
                self.scf_max_cycles
            ):
                # increase number of cycles if not already set or is different
                # from scf_max_cycles
                self.gin.route_parameters["scf"]["maxcycle"] = self.scf_max_cycles
                actions.append({"scf_max_cycles": self.scf_max_cycles})

            elif not {"xqc", "yqc", "qc"}.intersection(
                self.gin.route_parameters.get("scf")
            ):
                # use an alternate SCF converger
                self.gin.route_parameters["scf"]["xqc"] = None
                actions.append({"scf_algorithm": "xqc"})

            elif (
                self.job_type == "better_guess"
                and not GaussianErrorHandler.activate_better_guess
            ):
                # try to get a better initial guess at a lower level of theory
                self.logger.info(
                    "SCF calculation failed. Switching to a lower "
                    "level of theory to get a better initial "
                    "guess of molecular orbitals"
                )
                # TODO: what if inputs don't work with scf_lot? e.g. extra_basis
                self.gin.functional = self.lower_functional
                self.gin.basis_set = self.lower_basis_set
                GaussianErrorHandler.activate_better_guess = True
                actions.append({"scf_level_of_theory": "better_scf_guess"})

            else:
                if self.job_type != "better_guess":
                    self.logger.info(
                        "Try to switch to better_guess job type to "
                        "generate a different initial guess using a "
                        "lower level of theory"
                    )
                else:
                    self.logger.info("SCF calculation failed. Exiting...")
                return {"errors": list[self.errors], "actions": None}

        elif "opt_steps" in self.errors:
            # int_actions = self._add_int()
            if self.gin.route_parameters.get("opt").get("maxcycles") != str(
                self.opt_max_cycles
            ):
                self.gin.route_parameters["opt"]["maxcycles"] = self.opt_max_cycles
                if len(self.gout.structures) > 1:
                    self.gin._mol = self.gout.final_structure
                    actions.append({"structure": "from_final_structure"})
                actions.append({"opt_max_cycles": self.opt_max_cycles})

            elif self.check_convergence and all(
                v[-1] < v[0] for v in self.conv_data["values"].values()
            ):
                self.gin._mol = self.gout.final_structure
                actions.append({"structure": "from_final_structure"})

            elif self._add_int():
                actions.append({"integral": "ultra_fine"})

            # elif int_actions:
            #     actions.append(int_actions)
            # TODO: check if the defined methods are clean
            # TODO: don't enter this if condition if g16 and ...

            elif (
                self.job_type == "better_guess"
                and not GaussianErrorHandler.activate_better_guess
            ):
                # TODO: check if the logic is correct since this is used with scf
                # try to get a better initial guess at a lower level of theory
                self.logger.info(
                    "Geometry optimiztion failed. Switching to a "
                    "lower level of theory to get a better "
                    "initial guess of molecular geometry"
                )
                self.gin.functional = self.lower_functional
                self.gin.basis_set = self.lower_basis_set
                GaussianErrorHandler.activate_better_guess = True
                actions.append({"opt_level_of_theory": "better_geom_guess"})

            else:
                # TODO: custodian file is empty if actions are None, why?
                if self.job_type != "better_guess":
                    self.logger.info(
                        "Try to switch to better_guess job type to "
                        "generate a different initial guess using a "
                        "lower level of theory"
                    )
                else:
                    self.logger.info("Geometry optimization failed. Exiting...")
                return {"errors": list(self.errors), "actions": None}

        elif "linear_bend" in self.errors:
            # if there is some linear bend around an angle in the geometry,
            # restart the job at the point it stopped while forcing Gaussian
            # to rebuild the set of redundant internals
            if not list(
                filter(
                    re.compile(r"%[Cc][Hh][Kk]").match, self.gin.link0_parameters.keys()
                )
            ):
                raise KeyError(
                    "This remedy reads coords from checkpoint "
                    "file. Consider adding CHK to link0_parameters"
                )
            else:
                self.gin = GaussianInput(
                    mol=None,
                    charge=self.gin.charge,
                    spin_multiplicity=self.gin.spin_multiplicity,
                    title=self.gin.title,
                    functional=self.gin.functional,
                    basis_set=self.gin.basis_set,
                    route_parameters=self.gin.route_parameters,
                    input_parameters=self.gin.input_parameters,
                    link0_parameters=self.gin.link0_parameters,
                    dieze_tag=self.gin.dieze_tag,
                    gen_basis=self.gin.gen_basis,
                )
                self.gin.route_parameters.update(
                    {"geom": "(checkpoint, newdefinition)"}
                )
                actions.append({"coords": "rebuild_redundant_internals"})

        elif "solute_solvent_surface" in self.errors:
            # if non-convergence in the iteration of the PCM matrix is
            # encountered, change the type of molecular surface representing
            # the solute-solvent boundary
            # TODO: test
            input_parms = {
                key.lower() if isinstance(key, str) else key: value
                for key, value in self.gin.input_parameters.items()
            }
            if input_parms.get("surface", "none").lower() != "sas":
                GaussianErrorHandler._update_route_params(
                    self.gin.route_parameters, "scrf", "read"
                )
                self.gin.input_parameters.update({"surface": "SAS"})
                actions.append({"surface": "SAS"})
            else:
                self.logger.info(
                    "Not sure how to fix "
                    "solute_solvent_surface_error if surface is "
                    "already SAS!"
                )
                return {"errors": [self.errors], "actions": None}

        elif "internal_coords" in self.errors:
            # check if optimization is requested to be performed in cartesian
            # coords. if not, set it while overwriting other possibly requested
            # coord systems, disable symmetry if applicable, and rerun
            # however, this will come at a higher computational cost
            if "opt" in self.gin.route_parameters and not any(
                n in (self.gin.route_parameters.get("opt") or {})
                for n in ["cart", "cartesian"]
            ):
                GaussianErrorHandler._update_route_params(
                    self.gin.route_parameters, "opt", "cartesian"
                )
                if isinstance(self.gin.route_parameters["opt"], dict):
                    [
                        self.gin.route_parameters["opt"].pop(i, None)
                        for i in ["redundant", "zmatrix", "z-matrix"]
                    ]

                if (
                    not self.gin.route_parameters.get("nosymmetry")
                    or self.gin.route_parameters.get("symmetry") != "none"
                ):
                    self.gin.route_parameters["symmetry"] = "none"
                    actions.append({"symmetry": False})
                actions.append({"opt_cart_coords": True})
            else:
                self.logger.info(
                    "An error occurred in internal coordinates. "
                    "Your molecule might have 3 or more atoms "
                    "that are nearly linear making it difficult "
                    "to generate internal coordinates. Try to "
                    "modify your structure input?"
                )
                return {"errors": [self.errors], "actions": None}

        elif "zmatrix" in self.errors:
            gfile = open(os.path.join(directory, self.input_file))
            lines = gfile.readlines()
            last_lines = lines[-2:]
            gfile.close()
            if not set(last_lines) == {"\n"}:
                # if the required blank lines at the end of the input file are
                # missing, just rewrite the file
                self.logger.info("Missing blank line at the end of the input " "file.")
                actions.append({"blank_lines": "rewrite_input_file"})
            else:
                self.logger.info(
                    "Not sure how to fix zmatrix error. " "Check manually?"
                )
                return {"errors": [self.errors], "actions": None}

        elif "coords" in self.errors:
            if "connectivity" in self.gin.route_parameters.get("geom"):
                self.logger.info(
                    "Explicit atom bonding is requested but no "
                    "such input is provided"
                )
                if (
                    isinstance(self.gin.route_parameters["geom"], dict)
                    and len(self.gin.route_parameters["geom"]) > 1
                ):
                    self.gin.route_parameters["geom"].pop("connectivity", None)
                else:
                    del self.gin.route_parameters["geom"]
                actions.append({"coords": "remove_connectivity"})
            else:
                self.logger.info(
                    "Missing connectivity info. Not sure how to "
                    "fix this error. Exiting!"
                )
                return {"errors": [self.errors], "actions": None}

        elif "found_coords" in self.errors:
            if self.gin.molecule and any(
                key in self.gin.route_parameters.get("geom", {})
                for key in ["checkpoint", "check", "allcheck"]
            ):
                # if coords are found in the input and the user chooses to read
                # the the molecule specification from the checkpoint file,
                # remove mol
                self.gin._mol = None
                actions.append({"mol": "remove_from_input"})
            else:
                self.logger.info(
                    "Not sure why atom specifications should not "
                    "be found in the input. Examine manually!"
                )
                return {"errors": [self.errors], "actions": None}

        elif "coord_inputs" in self.errors:
            if (
                any(
                    key in self.gin.route_parameters.get("opt", {})
                    for key in ["z-matrix", "zmatrix"]
                )
                and self.cart_coords
            ):
                # if molecule is specified in xyz format, but the user chooses
                # to perform the optimization using internal coordinates,
                # switch to z-matrix format
                self.cart_coords = False
                actions.append({"coords": "use_zmatrix_format"})
            else:
                # error cannot be fixed automatically. Return None for actions
                self.logger.info(
                    "Not sure how to fix problem with z-matrix "
                    "optimization if coords are already input in"
                    "z-matrix format. Examine manually!"
                )
                return {"errors": [self.errors], "actions": None}

        elif "missing_mol" in self.errors:
            if (
                not self.gin.molecule
                and "read" in self.gin.route_parameters.get("guess")
                and not any(
                    key in self.gin.route_parameters.get("geom", {})
                    for key in ["checkpoint", "check", "allcheck"]
                )
            ):
                # if molecule is not specified and the user requests that the
                # initial guess be read from the checkpoint file but forgot to
                # take the geom from the checkpoint file, add geom=check
                if not glob.glob("*.[Cc][Hh][Kk]"):
                    raise FileNotFoundError(
                        "This remedy reads geometry from "
                        "checkpoint file. This file is "
                        "missing!"
                    )
                GaussianErrorHandler._update_route_params(
                    self.gin.route_parameters, "geom", "check"
                )
                self.gin.route_parameters["geom"] = "check"
                actions.append({"mol": "get_from_checkpoint"})
            else:
                # error cannot be fixed automatically. Return None for actions
                self.logger.info(
                    "Molecule is not found in the input file. " "Fix manually!"
                )
                # TODO: check if logger.info is enough here or return is needed
                return {"errors": list(self.errors), "actions": None}

        elif any(err in self.errors for err in ["empty_file", "bad_file"]):
            self.logger.error("Required checkpoint file is bad. Fix " "manually!")
            return {"errors": list(self.errors), "actions": None}

        elif "missing_file" in self.errors:
            self.logger.error("Could not find the required file. Fix manually!")
            return {"errors": list(self.errors), "actions": None}

        elif "syntax" in self.errors:
            # error cannot be fixed automatically. Return None for actions
            self.logger.info(
                "A syntax error was detected in the input file. " "Fix manually!"
            )
            return {"errors": list(self.errors), "actions": None}

        elif "insufficient_mem" in self.errors:
            mem_key, dynamic_mem = GaussianErrorHandler._find_dynamic_memory_allocated(
                self.gin.link0_parameters
            )
            if dynamic_mem and self.recom_mem and dynamic_mem < self.recom_mem:
                # this assumes that 1.5*minimum required memory is available
                mem = math.ceil(self.recom_mem * 1.5)
                self.gin.link0_parameters[mem_key] = f"{mem}MB"
                actions.append({"memory": "increase_to_gaussian_recommendation"})
            else:
                self.logger.info(
                    "Check job memory requirements manually and " "set as needed."
                )
                return {"errors": list(self.errors), "actions": None}

        else:
            self.logger.info(
                "Must have gotten an error that is parsed but not "
                "handled yet. Fix manually!"
            )
            return {"errors": list(self.errors), "actions": None}

        os.rename(
            os.path.join(directory, self.input_file),
            os.path.join(directory, self.input_file + ".prev"),
        )
        self.gin.write_file(os.path.join(directory, self.input_file), self.cart_coords)
        # TODO: ADDED
        if os.path.exists(os.path.join(directory, self.input_file) + ".wt"):
            shutil.copyfile(
                os.path.join(directory, self.input_file),
                os.path.join(directory, self.input_file + ".wt"),
            )
        return {"errors": list(self.errors), "actions": actions}


class WalTimeErrorHandler(ErrorHandler):
    is_monitor = True

    def __init__(
        self,
        wall_time,
        buffer_time,
        input_file,
        output_file,
        stderr_file="stderr.txt",
        prefix="error",
    ):
        self.wall_time = wall_time
        self.buffer_time = buffer_time
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.prefix = prefix
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)

        now_ = datetime.datetime.now()
        now_str = datetime.datetime.strftime(now_, "%a %b %d %H:%M:%S UTC %Y")

        self.init_time = os.environ.get("JOB_START_TIME", now_str)
        os.environ["JOB_START_TIME"] = self.init_time
        self.init_time = datetime.datetime.strptime(
            self.init_time, "%a %b %d %H:%M:%S %Z %Y"
        )

    def check(self, directory="./"):
        if self.wall_time:
            run_time = datetime.datetime.now() - self.init_time
            remaining_time = self.wall_time - run_time.total_seconds()
            if remaining_time <= self.buffer_time:
                return True
        return False

    def correct(self, directory="./"):
        # TODO: when using restart, the rwf file might be in a different dir
        backup_files = [self.input_file, self.output_file, self.stderr_file] + list(
            BACKUP_FILES.values()
        )
        backup(backup_files, prefix=self.prefix, directory=directory)
        if glob.glob(os.path.join(directory, BACKUP_FILES["rwf"])):
            rwf = glob.glob(os.path.join(directory, BACKUP_FILES["rwf"]))[0]
            gin = GaussianInput.from_file(os.path.join(directory, self.input_file))
            # TODO: check if rwf is already there like RWF or Rwf or ...
            # gin.link0_parameters.update({'%rwf': rwf})
            # gin.route_parameters = {'Restart': None}
            # os.rename(self.input_file, self.input_file + '.prev')
            input_str = [f"%rwf={rwf}"] + [
                f"{i}={j}" for i, j in gin.link0_parameters.items()
            ]
            input_str.append(f"{gin.dieze_tag} Restart\n\n")
            with open(os.path.join(directory, self.input_file + ".wt"), "w") as f:
                f.write("\n".join(input_str))
            return {"errors": ["wall_time_limit"], "actions": None}
        else:
            self.logger.info(
                "Wall time handler requires a read-write gaussian "
                "file to be available. No such file is found."
            )
