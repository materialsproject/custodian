"""This module implements error handlers for Gaussian runs."""

from __future__ import annotations

import datetime
import glob
import logging
import math
import os
import re
import shutil
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from monty.io import zopen
from pymatgen.io.gaussian import GaussianInput, GaussianOutput

from custodian.custodian import ErrorHandler
from custodian.utils import backup

if TYPE_CHECKING:
    from collections.abc import Iterable

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


class GaussianErrorHandler(ErrorHandler):
    """
    Master GaussianErrorHandler class that handles a number of common errors that occur
    during Gaussian runs.
    """

    # definition of job errors as they appear in Gaussian output file
    error_defs: ClassVar = {
        "Optimization stopped": "opt_steps",
        "Convergence failure": "scf_convergence",
        "FormBX had a problem": "linear_bend",
        "Linear angle in Tors.": "linear_bend",
        "Inv3 failed in PCMMkU": "solute_solvent_surface",
        "Error in internal coordinate system": "internal_coords",
        "End of file in ZSymb": "zmatrix",
        "There are no atoms in this input structure !": "missing_mol",
        "Atom specifications unexpectedly found in input stream.": "found_coords",
        "End of file reading connectivity.": "coords",
        "FileIO operation on non-existent file.": "missing_file",
        "No data on chk file.": "empty_file",
        "Bad file opened by FileIO": "bad_file",
        "Z-matrix optimization but no Z-matrix variables.": "coord_inputs",
        "A syntax error was detected in the input line.": "syntax",
        r"The combination of multiplicity ([0-9]+) and \s+? ([0-9]+) electrons is impossible.": "charge",
        "Out-of-memory error in routine": "insufficient_mem",
    }

    error_patt = re.compile("|".join(list(error_defs)))
    recom_mem_patt = re.compile(
        r"Use %mem=([0-9]+)MW to provide the minimum amount of memory required to complete this step."
    )
    conv_criteria: ClassVar = {
        "max_force": re.compile(r"\s+(Maximum Force)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"),
        "rms_force": re.compile(r"\s+(RMS {5}Force)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"),
        "max_disp": re.compile(r"\s+(Maximum Displacement)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"),
        "rms_disp": re.compile(r"\s+(RMS {5}Displacement)\s+(-?\d+.?\d*|.*)\s+(-?\d+.?\d*)"),
    }

    grid_patt = re.compile(r"(-?\d{5})")
    GRID_NAMES = (
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
    )
    MEM_UNITS = ("kb", "mb", "gb", "tb", "kw", "mw", "gw", "tw")

    activate_better_guess = False

    def __init__(
        self,
        input_file: str,
        output_file: str,
        stderr_file: str = "stderr.txt",
        cart_coords: bool = True,
        scf_max_cycles: int = 100,
        opt_max_cycles: int = 100,
        job_type: str = "normal",
        lower_functional: str | None = None,
        lower_basis_set: str | None = None,
        prefix: str = "error",
        check_convergence: bool = True,
    ):
        """
        Initialize the GaussianErrorHandler class.

        Args:
            input_file (str): The name of the input file for the Gaussian job.
            output_file (str): The name of the output file for the Gaussian job.
            stderr_file (str): The name of the standard error file for the Gaussian job.
                Defaults to 'stderr.txt'.
            cart_coords (bool): Whether the coordinates are in cartesian format.
                Defaults to True.
            scf_max_cycles (int): The maximum number of SCF cycles. Defaults to 100.
            opt_max_cycles (int): The maximum number of optimization cycles. Defaults to
                100.
            job_type (str): The type of job to run. Supported options are 'normal' and
                'better_guess'. Defaults to 'normal'. If 'better_guess' is chosen, the
                job will be rerun at a lower level of theory to get a better initial
                guess of molecular orbitals or geometry, if needed.
            lower_functional (str): The lower level of theory to use for a better guess.
            lower_basis_set (str): The lower basis set to use for a better guess.
            prefix (str): The prefix to use for the backup files. Defaults to error,
                which means a series of error.1.tar.gz, error.2.tar.gz, ... will be
                generated.
            check_convergence (bool): Whether to check for convergence during an
                optimization job. Defaults to True. If True, the convergence data will
                be monitored and plotted (convergence criteria versus cycle number) and
                saved to a file called 'convergence.png'.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.cart_coords = cart_coords
        self.errors: set[str] = set()
        self.scf_max_cycles = scf_max_cycles
        self.opt_max_cycles = opt_max_cycles
        self.job_type = job_type
        self.lower_functional = lower_functional
        self.lower_basis_set = lower_basis_set
        self.prefix = prefix
        self.check_convergence = check_convergence
        self.conv_data: dict[str, dict[str, Any]] = {}
        self.recom_mem: float | None = None
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)

    @staticmethod
    def _recursive_lowercase(obj: dict[str, Any] | str | Iterable[Any]) -> dict[str, Any] | str | Iterable[Any]:
        """
        Recursively convert all string elements in a given object to lowercase.

        This method iterates over the input object. If the object is a dictionary, it
        converts all its string keys and values to lowercase, applying the same logic
        recursively to the values. If the object is a string, it directly converts it
        to lowercase. If the object is iterable (but not a string or dictionary), it
        applies the same lowercase conversion to each element in the iterable. For all
        other types, the object is returned unchanged.

        Args:
            obj (dict | str | iterable): The object to be converted to lowercase.
                This can be a dictionary, a string, or any iterable collection.
                Non-iterable objects or non-string elements within iterables are
                returned unchanged.

        Returns:
            dict | str | iterable:
                A new object with all string elements converted to
                lowercase. The type of the returned object matches the type of the
                input `obj`.
        """
        if isinstance(obj, dict):
            return {k.lower(): GaussianErrorHandler._recursive_lowercase(v) for k, v in obj.items()}
        if isinstance(obj, str):
            return obj.lower()
        if hasattr(obj, "__iter__"):
            return [GaussianErrorHandler._recursive_lowercase(i) for i in obj]
        return obj

    @staticmethod
    def _recursive_remove_space(obj: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively remove leading and trailing whitespace from keys and string values
        in a dictionary.

        This method processes each key-value pair in the given dictionary. If a value
        is a string, it strips leading and trailing whitespace from it. If a value is
        a dictionary, it applies the same stripping process recursively to that
        dictionary. The keys of the dictionary are also stripped of leading and trailing
        whitespace. Non-string values are included in the output without modification.

        Args:
            obj (dict): The dictionary whose keys and string values will have whitespace
                removed. It can be nested, with dictionaries as values, which will
                also be processed.

        Returns:
            dict:
                A new dictionary with all keys and string values stripped of leading
                and trailing whitespace. The structure of the dictionary is preserved.
        """
        return {
            key.strip(): GaussianErrorHandler._recursive_remove_space(value)
            if isinstance(value, dict)
            else value.strip()
            if isinstance(value, str)
            else value
            for key, value in obj.items()
        }

    @staticmethod
    def _update_route_params(route_params: dict, key: str, value: str | dict) -> dict:
        """
        Update Gaussian route parameters with new key-value pairs, handling nested
        structures.

        Args:
            route_params (dict): The dictionary of route parameters to be updated.
            key (str): The key in the route parameters to update or add.
            value (str | dict): The new value to set or add to the route parameters.
                This can be a string or a dictionary. If it is a dictionary, it is
                merged with the existing dictionary at `key`.

        Returns:
            dict:
                The updated route parameters.
        """
        obj = route_params.get(key, {})
        if not obj:
            route_params[key] = value
        elif isinstance(obj, str):
            update = {key: {obj: None, **value}} if isinstance(value, dict) else {key: {obj: None, value: None}}
            route_params.update(update)
        elif isinstance(obj, dict):
            route_params[key].update(value if isinstance(value, dict) else {value: None})
        return route_params

    @staticmethod
    def _int_keyword(route_params: dict[str, str | dict]) -> tuple[str, str | dict]:
        """
        Determine the keyword used for 'Integral' in the Gaussian route parameters of
        the input file. Possible keywords are 'int' and 'integral'. If neither keyword
        is found, an empty string is returned.

        Args:
            route_params (dict): The route parameters dictionary.

        Returns:
            tuple:
                The key ('int' or 'integral' or an empty string if neither is found),
                and the value associated with this key in `route_params`. If the key is
                not found, the second element in the tuple is an empty string.
        """
        if "int" in route_params:
            int_key = "int"
        elif "integral" in route_params:
            int_key = "integral"
        else:
            int_key = ""
        # int_key = 'int' if 'int' in route_params else 'integral'
        return int_key, route_params.get(int_key, "")

    @staticmethod
    def _int_grid(route_params: dict[str, str | dict]) -> bool:
        """
        Check if the integration grid used for numerical integrations matches specific
        options.

        Args:
            route_params (dict): The route parameters dictionary.

        Returns:
            bool:
                True if the integral grid parameter matches one of the predefined
                options, otherwise False.
        """
        _, int_value = GaussianErrorHandler._int_keyword(route_params)
        options = ["ultrafine", "ultrafinegrid", "99590"]

        if isinstance(int_value, str) and int_value in options:
            return True
        if isinstance(int_value, dict):
            if int_value.get("grid") in options:
                return True
            if set(int_value) & set(options):
                return True
        return False

    @staticmethod
    def convert_mem(mem: float, unit: str) -> float:
        """
        Convert memory size between different units to megabytes (MB).

        Args:
            mem (float): The memory size to convert.
            unit (str): The unit of the input memory size. Supported units include
                'kb', 'mb', 'gb', 'tb', and word units ('kw', 'mw', 'gw', 'tw'), or an
                empty string for default conversion (from words).

        Returns:
            float:
                The memory size in MB.
        """
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
    def _find_dynamic_memory_allocated(link0_params: dict[str, str]) -> tuple[str | None, float | None]:
        """
        Find and convert the memory allocation from Gaussian link0 parameters. This
        method searches for the '%mem' key in the link0 parameters of a Gaussian job
        to determine the memory allocated for the job. It extracts the memory value
        and its unit, then converts the  memory allocation to MB. The default memory
        unit used in Gaussian is words, and this method accounts for different units
        specified in the memory string.

        Args:
            link0_params (dict): A dictionary of link0 parameters from a Gaussian input
                file.

        Returns:
            tuple:
                The memory key (None if '%mem' is not found) and the converted memory
                allocation in MB. If '%mem' is not found, the second element will be None.
        """
        mem_key = None
        dynamic_mem = None
        for k in link0_params:
            if k.lower() == "%mem":
                mem_key = k
                break
        if mem_key:
            dynamic_mem_str = link0_params[mem_key]
            # default memory unit in Gaussian is words
            dynamic_mem_str = dynamic_mem_str.lower()
            mem_unit = ""
            for unit in GaussianErrorHandler.MEM_UNITS:
                if unit in dynamic_mem_str:
                    mem_unit = unit
                    break
            dynamic_mem = float(dynamic_mem_str.strip(mem_unit))
            dynamic_mem = GaussianErrorHandler.convert_mem(dynamic_mem, mem_unit)
        return mem_key, dynamic_mem

    def _add_int(self) -> bool:
        """
        Check and update the integration grid setting ('int') in the Gaussian input
        file's route parameters to 'ultrafine', if necessary.

        Returns:
            bool: True if changes were made to the integration grid setting, False otherwise.
        """
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

            int_key, int_value = GaussianErrorHandler._int_keyword(self.gin.route_parameters)
            if not int_value and GaussianErrorHandler._not_g16(self.gout):
                # if int keyword is missing and Gaussian version is 03 or
                # 09, set integration grid to ultrafine
                int_key = int_key or "int"
                self.logger.warning(warning_msg)
                self.gin.route_parameters[int_key] = "ultrafine"
                return True
            if isinstance(int_value, dict):
                # if int grid is set and is different from ultrafine,
                # set it to ultrafine (works when others int options are
                # specified)
                flag = False
                if "grid" in self.gin.route_parameters[int_key]:
                    flag = True
                for key in self.gin.route_parameters[int_key]:
                    if key in self.GRID_NAMES or self.grid_patt.match(key):
                        self.gin.route_parameters[int_key].pop(key)
                        flag = True
                        break
                if flag or GaussianErrorHandler._not_g16(self.gout):
                    self.logger.warning(warning_msg)
                    self.gin.route_parameters[int_key]["grid"] = "ultrafine"
                    return True
            if isinstance(int_value, str) and (int_value in self.GRID_NAMES or self.grid_patt.match(int_value)):
                # if int grid is set and is different from ultrafine,
                # set it to ultrafine (works when no other int options
                # are specified)
                self.logger.warning(warning_msg)
                self.gin.route_parameters[int_key] = "ultrafine"
                return True
            if GaussianErrorHandler._not_g16(self.gout):
                # if int grid is not specified, and Gaussian version is
                # not 16, update with ultrafine integral grid
                self.logger.warning(warning_msg)
                GaussianErrorHandler._update_route_params(self.gin.route_parameters, int_key, {"grid": "ultrafine"})
                return True
            return False
        return False

    @staticmethod
    def _not_g16(gout: GaussianOutput) -> bool:
        """
        Determine if the Gaussian version is not 16.

        Args:
        gout (GaussianOutput): A GaussianOutput object.

        Returns:
            bool: True if the Gaussian version is not 16, False otherwise.
        """
        return "16" not in gout.version  # type:ignore[attr-defined]

    @staticmethod
    def _monitor_convergence(data: dict[str, dict[str, Any]], directory: str = "./") -> None:
        """
        Plot and save a convergence graph for an optimization job as a function of the
        number of iterations.

        Parameters:
        data (dict): A dictionary containing two keys: 'values' and 'thresh'. 'values'
            is a dictionary where each key-value pair represents a parameter and its
            values across iterations. 'thresh' is a dictionary where each key-value pair
            represents a parameter and its threshold value. The convergence parameters
            are: 'max_force', 'rms_force', 'max_disp', and 'rms_disp'.
        directory (str, optional): The directory where the convergence plot image will
            be saved. Defaults to "./".
        """
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MaxNLocator

        _fig, ax = plt.subplots(ncols=2, nrows=2, figsize=(12, 10))
        for i, (k, v) in enumerate(data["values"].items()):
            row = int(np.floor(i / 2))
            col = i % 2
            iters = range(len(v))
            ax[row, col].plot(iters, v, color="#cf3759", linewidth=2)
            ax[row, col].axhline(y=data["thresh"][k], linewidth=2, color="black", linestyle="--")
            ax[row, col].tick_params(which="major", length=8)
            ax[row, col].tick_params(axis="both", which="both", direction="in", labelsize=16)
            ax[row, col].set_xlabel("Iteration", fontsize=16)
            ax[row, col].set_ylabel(f"{k}", fontsize=16)
            ax[row, col].xaxis.set_major_locator(MaxNLocator(integer=True))
            ax[row, col].grid(ls="--", zorder=1)
        plt.tight_layout()
        plt.savefig(os.path.join(directory, "convergence.png"))

    def check(self, directory: str = "./") -> bool:
        """Check for errors in the Gaussian output file."""
        # TODO: this backups the original file instead of the actual one
        if "linear_bend" in self.errors:
            os.rename(
                os.path.join(directory, self.input_file + ".prev"),
                os.path.join(directory, self.input_file),
            )

        self.gin = GaussianInput.from_file(os.path.join(directory, self.input_file))
        self.gin.route_parameters = GaussianErrorHandler._recursive_lowercase(self.gin.route_parameters)
        assert isinstance(self.gin.route_parameters, dict)
        self.gin.route_parameters = GaussianErrorHandler._recursive_remove_space(self.gin.route_parameters)
        self.gout = GaussianOutput(os.path.join(directory, self.output_file))
        self.errors = set()
        error_patts = set()
        # TODO: move this to pymatgen?
        self.conv_data = {"values": {}, "thresh": {}}
        with zopen(os.path.join(directory, self.output_file), "rt", encoding="utf-8") as f:
            for line in f:
                error_match = GaussianErrorHandler.error_patt.search(line)  # type:ignore[arg-type]
                mem_match = GaussianErrorHandler.recom_mem_patt.search(line)  # type:ignore[arg-type]
                if error_match:
                    patt = error_match.group(0)
                    error_patts.add(patt)
                    for pattern, error_key in GaussianErrorHandler.error_defs.items():
                        if re.match(pattern, patt):
                            self.errors.add(error_key)
                            break
                    # self.errors.add(GaussianErrorHandler.error_defs[patt])
                if mem_match:
                    mem = mem_match.group(1)
                    self.recom_mem = GaussianErrorHandler.convert_mem(float(mem), "mw")

                if self.check_convergence and "opt" in self.gin.route_parameters:
                    for k, v in GaussianErrorHandler.conv_criteria.items():
                        m = v.search(line)
                        if m:
                            if k not in self.conv_data["values"]:
                                self.conv_data["values"][k] = [m.group(2)]
                                self.conv_data["thresh"][k] = float(m.group(3))
                            else:
                                self.conv_data["values"][k].append(m.group(2))

        # TODO: it only plots after the job finishes, modify?
        if self.conv_data["values"] and all(len(v) >= 2 for v in self.conv_data["values"].values()):
            for k, v in self.conv_data["values"].items():
                # convert strings to float taking into account the
                # possibility of having ******** values
                self.conv_data["values"][k] = np.genfromtxt(np.array(v))
            GaussianErrorHandler._monitor_convergence(self.conv_data)
        for patt in error_patts:
            self.logger.error(patt)
        return len(self.errors) > 0

    def correct(self, directory: str = "./"):
        """Perform necessary actions to correct the errors in the Gaussian output."""
        actions: list[Any] = []
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
        backup_files = [self.input_file, self.output_file, self.stderr_file, *BACKUP_FILES.values()]
        backup(backup_files, prefix=self.prefix, directory=directory)
        if "scf_convergence" in self.errors:
            self.gin.route_parameters = GaussianErrorHandler._update_route_params(self.gin.route_parameters, "scf", {})
            # if the SCF procedure has failed to converge
            if self.gin.route_parameters.get("scf", {}).get("maxcycle") != str(self.scf_max_cycles):
                # increase number of cycles if not already set or is different
                # from scf_max_cycles
                self.gin.route_parameters["scf"]["maxcycle"] = self.scf_max_cycles
                actions.append({"scf_max_cycles": self.scf_max_cycles})

            elif not {"xqc", "yqc", "qc"}.intersection(self.gin.route_parameters.get("scf", set())):
                # use an alternate SCF converger
                self.gin.route_parameters["scf"]["xqc"] = None
                actions.append({"scf_algorithm": "xqc"})

            elif self.job_type == "better_guess" and not GaussianErrorHandler.activate_better_guess:
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
                return {"errors": list(self.errors), "actions": None}

        elif "opt_steps" in self.errors:
            # int_actions = self._add_int()
            if self.gin.route_parameters.get("opt").get("maxcycles") != str(self.opt_max_cycles):
                self.gin.route_parameters["opt"]["maxcycles"] = self.opt_max_cycles
                if len(self.gout.structures) > 1:
                    self.gin._mol = self.gout.final_structure
                    actions.append({"structure": "from_final_structure"})
                actions.append({"opt_max_cycles": self.opt_max_cycles})

            elif self.check_convergence and all(v[-1] < v[0] for v in self.conv_data["values"].values()):
                self.gin._mol = self.gout.final_structure
                actions.append({"structure": "from_final_structure"})

            elif self._add_int():
                actions.append({"integral": "ultra_fine"})

            # elif int_actions:
            #     actions.append(int_actions)
            # TODO: check if the defined methods are clean
            # TODO: don't enter this if condition if g16 and ...

            elif self.job_type == "better_guess" and not GaussianErrorHandler.activate_better_guess:
                # TODO: check if the logic is correct since this is used with scf
                # try to get a better initial guess at a lower level of theory
                self.logger.info(
                    "Geometry optimization failed. Switching to a "
                    "lower level of theory to get a better "
                    "initial guess of molecular geometry"
                )
                self.gin.functional = self.lower_functional
                self.gin.basis_set = self.lower_basis_set
                GaussianErrorHandler.activate_better_guess = True
                actions.append({"opt_level_of_theory": "better_geom_guess"})

            else:
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
            if not list(filter(re.compile(r"%[Cc][Hh][Kk]").match, self.gin.link0_parameters.keys())):
                raise KeyError("This remedy reads coords from checkpoint file. Consider adding CHK to link0_parameters")
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
            self.gin.route_parameters.update({"geom": "(checkpoint, newdefinition)"})
            actions.append({"coords": "rebuild_redundant_internals"})

        elif "solute_solvent_surface" in self.errors:
            # if non-convergence in the iteration of the PCM matrix is
            # encountered, change the type of molecular surface representing
            # the solute-solvent boundary
            # TODO: test
            input_parms = {
                key.lower() if isinstance(key, str) else key: value for key, value in self.gin.input_parameters.items()
            }
            if input_parms.get("surface", "none").lower() != "sas":
                GaussianErrorHandler._update_route_params(self.gin.route_parameters, "scrf", "read")
                self.gin.input_parameters.update({"surface": "SAS"})
                actions.append({"surface": "SAS"})
            else:
                self.logger.info("Not sure how to fix solute_solvent_surface_error if surface is already SAS!")
                return {"errors": [self.errors], "actions": None}

        elif "internal_coords" in self.errors:
            # check if optimization is requested to be performed in cartesian
            # coords. if not, set it while overwriting other possibly requested
            # coord systems, disable symmetry if applicable, and rerun
            # however, this will come at a higher computational cost
            if "opt" in self.gin.route_parameters and not any(
                n in (self.gin.route_parameters.get("opt") or {}) for n in ["cart", "cartesian"]
            ):
                GaussianErrorHandler._update_route_params(self.gin.route_parameters, "opt", "cartesian")
                if isinstance(self.gin.route_parameters["opt"], dict):
                    [self.gin.route_parameters["opt"].pop(i, None) for i in ["redundant", "zmatrix", "z-matrix"]]

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
            with open(os.path.join(directory, self.input_file)) as gfile:
                lines = gfile.readlines()
                last_lines = lines[-2:]
            if set(last_lines) != {"\n"}:
                # if the required blank lines at the end of the input file are
                # missing, just rewrite the file
                self.logger.info("Missing blank line at the end of the input file.")
                actions.append({"blank_lines": "rewrite_input_file"})
            else:
                self.logger.info("Not sure how to fix zmatrix error. Check manually?")
                return {"errors": [self.errors], "actions": None}

        elif "coords" in self.errors:
            if "connectivity" in self.gin.route_parameters.get("geom"):
                self.logger.info("Explicit atom bonding is requested but no such input is provided")
                if isinstance(self.gin.route_parameters["geom"], dict) and len(self.gin.route_parameters["geom"]) > 1:
                    self.gin.route_parameters["geom"].pop("connectivity", None)
                else:
                    del self.gin.route_parameters["geom"]
                actions.append({"coords": "remove_connectivity"})
            else:
                self.logger.info("Missing connectivity info. Not sure how to fix this error. Exiting!")
                return {"errors": [self.errors], "actions": None}

        elif "found_coords" in self.errors:
            if self.gin.molecule and any(
                key in self.gin.route_parameters.get("geom", {}) for key in ["checkpoint", "check", "allcheck"]
            ):
                # if coords are found in the input and the user chooses to read
                # the molecule specification from the checkpoint file,
                # remove mol
                self.gin._mol = None
                actions.append({"mol": "remove_from_input"})
            else:
                self.logger.info("Not sure why atom specifications should not be found in the input. Examine manually!")
                return {"errors": [self.errors], "actions": None}

        elif "coord_inputs" in self.errors:
            if (
                any(key in self.gin.route_parameters.get("opt", {}) for key in ["z-matrix", "zmatrix"])
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
                    key in self.gin.route_parameters.get("geom", {}) for key in ["checkpoint", "check", "allcheck"]
                )
            ):
                # if molecule is not specified and the user requests that the
                # initial guess be read from the checkpoint file but forgot to
                # take the geom from the checkpoint file, add geom=check
                if not glob.glob("*.[Cc][Hh][Kk]"):
                    raise FileNotFoundError("This remedy reads geometry from checkpoint file. This file is missing!")
                GaussianErrorHandler._update_route_params(self.gin.route_parameters, "geom", "check")
                self.gin.route_parameters["geom"] = "check"
                actions.append({"mol": "get_from_checkpoint"})
            else:
                # error cannot be fixed automatically. Return None for actions
                self.logger.info("Molecule is not found in the input file. Fix manually!")
                # TODO: check if logger.info is enough here or return is needed
                return {"errors": list(self.errors), "actions": None}

        elif any(err in self.errors for err in ["empty_file", "bad_file"]):
            self.logger.error("Required checkpoint file is bad. Fix manually!")
            return {"errors": list(self.errors), "actions": None}

        elif "missing_file" in self.errors:
            self.logger.error("Could not find the required file. Fix manually!")
            return {"errors": list(self.errors), "actions": None}

        elif "syntax" in self.errors:
            # error cannot be fixed automatically. Return None for actions
            self.logger.info("A syntax error was detected in the input file. Fix manually!")
            return {"errors": list(self.errors), "actions": None}

        elif "insufficient_mem" in self.errors:
            mem_key, dynamic_mem = GaussianErrorHandler._find_dynamic_memory_allocated(self.gin.link0_parameters)
            if dynamic_mem and self.recom_mem and dynamic_mem < self.recom_mem:
                # this assumes that 1.5*minimum required memory is available
                mem = math.ceil(self.recom_mem * 1.5)
                self.gin.link0_parameters[mem_key] = f"{mem}MB"
                actions.append({"memory": "increase_to_gaussian_recommendation"})
            else:
                self.logger.info("Check job memory requirements manually and set as needed.")
                return {"errors": list(self.errors), "actions": None}

        else:
            self.logger.info("Must have gotten an error that is parsed but not handled yet. Fix manually!")
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


class WallTimeErrorHandler(ErrorHandler):
    """
    Check if a run is nearing the walltime. If so, terminate the job and restart from
    the last .rwf file. A job is considered to be nearing the walltime if the remaining
    time is less than or equal to the buffer time.
    """

    is_monitor: bool = True

    def __init__(
        self,
        wall_time: int,
        buffer_time: int,
        input_file: str,
        output_file: str,
        stderr_file: str = "stderr.txt",
        prefix: str = "error",
    ):
        """
        Initialize the WalTimeErrorHandler class.

        Args:
            wall_time (int): The total wall time for the job in seconds.
            buffer_time (int): The buffer time in seconds. If the remaining time is less
                than or equal to the buffer time, the job is considered to be nearing the
                walltime and will be terminated.
            input_file (str): The name of the input file for the Gaussian job.
            output_file (str): The name of the output file for the Gaussian job.
            stderr_file (str): The name of the standard error file for the Gaussian job.
                Defaults to 'stderr.txt'.
            prefix (str): The prefix to use for the backup files. Defaults to error,
                which means a series of error.1.tar.gz, error.2.tar.gz, ... will be
                generated.
        """
        self.wall_time = wall_time
        self.buffer_time = buffer_time
        self.input_file = input_file
        self.output_file = output_file
        self.stderr_file = stderr_file
        self.prefix = prefix
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)

        now_ = datetime.datetime.now()
        now_str = datetime.datetime.strftime(now_, "%a %b %d %H:%M:%S UTC %Y")
        init_time_str = os.environ.get("JOB_START_TIME", now_str)
        os.environ["JOB_START_TIME"] = init_time_str
        self.init_time = datetime.datetime.strptime(init_time_str, "%a %b %d %H:%M:%S %Z %Y")

    def check(self, directory: str = "./") -> bool:
        """Check if the job is nearing the walltime. If so, return True, else False."""
        if self.wall_time:
            run_time = datetime.datetime.now() - self.init_time
            remaining_time = self.wall_time - run_time.total_seconds()
            if remaining_time <= self.buffer_time:
                return True
        return False

    def correct(self, directory: str = "./") -> dict:
        """Perform the corrections."""
        # TODO: when using restart, the rwf file might be in a different dir
        backup_files = [self.input_file, self.output_file, self.stderr_file, *BACKUP_FILES.values()]
        backup(backup_files, prefix=self.prefix, directory=directory)
        if glob.glob(os.path.join(directory, BACKUP_FILES["rwf"])):
            rwf = glob.glob(os.path.join(directory, BACKUP_FILES["rwf"]))[0]
            gin = GaussianInput.from_file(os.path.join(directory, self.input_file))
            # TODO: check if rwf is already there like RWF or Rwf or ...
            # gin.link0_parameters.update({'%rwf': rwf})
            # gin.route_parameters = {'Restart': None}
            # os.rename(self.input_file, self.input_file + '.prev')
            input_str = [f"%rwf={rwf}"] + [f"{i}={j}" for i, j in gin.link0_parameters.items()]
            input_str.append(f"{gin.dieze_tag} Restart\n\n")
            with open(os.path.join(directory, self.input_file + ".wt"), "w") as f:
                f.write("\n".join(input_str))
            return {"errors": ["wall_time_limit"], "actions": None}
        self.logger.info(
            "Wall time handler requires a read-write gaussian file to be available. No such file is found."
        )
        return {"errors": ["Walltime reached but not rwf file found"], "actions": None}
