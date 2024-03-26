"""This module implements error handlers for QChem runs."""

import os

from pymatgen.io.qchem.inputs import QCInput
from pymatgen.io.qchem.outputs import QCOutput

from custodian.custodian import ErrorHandler
from custodian.utils import backup

try:
    from openbabel import openbabel as ob
except ImportError:
    ob = None

__author__ = "Samuel Blau, Brandon Wood, Shyam Dwaraknath, Ryan Kingsbury"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "3/26/18"
__credits__ = "Xiaohui Qu"


class QChemErrorHandler(ErrorHandler):
    """
    Master QChemErrorHandler class that handles a number of common errors
    that occur during QChem runs.
    """

    is_monitor = False

    def __init__(
        self,
        input_file="mol.qin",
        output_file="mol.qout",
        scf_max_cycles=100,
        geom_max_cycles=200,
    ):
        """Initialize the error handler from a set of input and output files.

        Args:
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            scf_max_cycles (int): The max iterations to set to fix SCF failure.
            geom_max_cycles (int): The max iterations to set to fix geometry
                optimization failure.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.scf_max_cycles = scf_max_cycles
        self.geom_max_cycles = geom_max_cycles
        self.outdata = None
        self.errors = []
        self.opt_error_history = []

    def check(self, directory="./"):
        """Checks output file for errors."""
        self._output_path = os.path.join(directory, self.output_file)
        self.outdata = QCOutput(self._output_path).data
        self.errors = self.outdata.get("errors")
        self.warnings = self.outdata.get("warnings")
        # If we aren't out of optimization cycles, but we were in the past, reset the history
        if "out_of_opt_cycles" not in self.errors and len(self.opt_error_history) > 0:
            self.opt_error_history = []
        # If we're out of optimization cycles and we have unconnected fragments, no need to handle any errors
        if "out_of_opt_cycles" in self.errors and self.outdata["structure_change"] == "unconnected_fragments":
            return False
        return len(self.errors) > 0

    def correct(self, directory="./"):
        """Perform corrections."""
        self._input_path = os.path.join(directory, self.input_file)
        self._output_path = os.path.join(directory, self.output_file)
        backup({self._input_path, self._output_path})
        actions = []
        self.qcinp = QCInput.from_file(self._input_path)

        if "SCF_failed_to_converge" in self.errors:
            # Given defaults, the first handlers will typically be skipped.
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            if (
                int(self.qcinp.rem.get("max_scf_cycles", 50)) < self.scf_max_cycles
                or self.qcinp.rem.get("thresh", "10") != "14"
            ):
                if int(self.qcinp.rem.get("max_scf_cycles", 50)) < self.scf_max_cycles:
                    self.qcinp.rem["max_scf_cycles"] = self.scf_max_cycles
                    actions.append({"max_scf_cycles": self.scf_max_cycles})
                if self.qcinp.rem.get("thresh", "10") != "14":
                    self.qcinp.rem["thresh"] = "14"
                    actions.append({"thresh": "14"})
            # Turn on GDM
            elif self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                self.qcinp.rem["scf_algorithm"] = "gdm"
                actions.append({"scf_algorithm": "gdm"})
                self.qcinp.rem["max_scf_cycles"] = "500"
                actions.append({"max_scf_cycles": "500"})
            # Ensure we have 500 cycles for GDM
            elif (
                self.qcinp.rem.get("scf_algorithm", "diis").lower() == "gdm"
                and self.qcinp.rem.get("max_scf_cycles") != "500"
            ):
                self.qcinp.rem["max_scf_cycles"] = "500"
                actions.append({"max_scf_cycles": "500"})
            # Try forcing a new initial guess at each iteration
            elif (
                self.qcinp.rem.get("scf_guess_always", "none").lower() != "true"
                and "molecule_from_last_geometry" in self.outdata
            ):
                self.qcinp.rem["scf_guess_always"] = "true"
                actions.append({"scf_guess_always": "true"})
            else:
                print("No remaining SCF error handlers!")

        elif "out_of_opt_cycles" in self.errors:
            # Given defaults, the first two handlers will typically be skipped.
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            # Check number of opt cycles. If less than geom_max_cycles, increase to that value
            # set last geom as new starting geom, make sure using DIIS_GDM for SCF and rerun.
            elif int(self.qcinp.rem.get("geom_opt_max_cycles", 50)) < self.geom_max_cycles:
                self.qcinp.rem["geom_opt_max_cycles"] = self.geom_max_cycles
                if str(self.qcinp.rem.get("geom_opt2", "none")) == "3" or self.outdata["version"] == "6":
                    self.qcinp.geom_opt["maxiter"] = self.geom_max_cycles  # pylint: disable=unsupported-assignment-operation
                actions.append({"geom_max_cycles:": self.geom_max_cycles})
                if "molecule_from_last_geometry" in self.outdata:
                    self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                    actions.append({"molecule": "molecule_from_last_geometry"})

            # Often can just get convergence by restarting from the geometry of the last cycle.
            # But we'll also save any structural changes that happened along the way.
            else:
                self.opt_error_history += [self.outdata["structure_change"]]
                if len(self.opt_error_history) > 1 and self.opt_error_history[-1] == "no_change":
                    # If no structural changes occurred in two consecutive optimizations,
                    # and we still haven't converged, then just exit. This is most common
                    # if two species are flying away from each other.
                    return {
                        "errors": self.errors,
                        "actions": None,
                        "opt_error_history": self.opt_error_history,
                    }
                self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})
                # Using GDM for SCF convergence also often helps.
                if self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                    self.qcinp.rem["scf_algorithm"] = "gdm"
                    actions.append({"scf_algorithm": "gdm"})
                    self.qcinp.rem["max_scf_cycles"] = "500"
                    actions.append({"max_scf_cycles": "500"})

        elif "unable_to_determine_lamda" in self.errors:
            # Given defaults, the first two handlers will typically be skipped.
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            elif "molecule_from_last_geometry" in self.outdata:
                self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})
                if self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                    self.qcinp.rem["scf_algorithm"] = "gdm"
                    actions.append({"scf_algorithm": "gdm"})
                    self.qcinp.rem["max_scf_cycles"] = "500"
                    actions.append({"max_scf_cycles": "500"})
            else:
                print("Not sure how to fix Lambda error in this case!")

        elif "back_transform_error" in self.errors or "svd_failed" in self.errors:
            # Given defaults, the first two handlers will typically be skipped.
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            elif "molecule_from_last_geometry" in self.outdata:
                self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})

            elif str(self.qcinp.rem.get("geom_opt2", "none")) == "3":
                self.qcinp.rem.pop("geom_opt2", None)
                self.qcinp.geom_opt = None
                actions.append({"geom_opt2": "deleted"})

            elif self.outdata["version"] == "6" and self.qcinp.rem.get("geom_opt_driver", "libopt3") != "optimize":
                if self.qcinp.geom_opt["coordinates"] == "redundant":
                    self.qcinp.geom_opt["coordinates"] = "delocalized"  # pylint: disable=unsupported-assignment-operation
                    actions.append({"coordinates": "delocalized"})
                    if self.qcinp.geom_opt.get("initial_hessian", "none") != "read":
                        self.qcinp.geom_opt["initial_hessian"] = "model"
                        actions.append({"initial_hessian": "model"})
                elif self.qcinp.geom_opt["coordinates"] == "delocalized":
                    self.qcinp.geom_opt["coordinates"] = "cartesian"  # pylint: disable=unsupported-assignment-operation
                    actions.append({"coordinates": "cartesian"})
                    if self.qcinp.geom_opt.get("initial_hessian", "none") == "model":
                        del self.qcinp.geom_opt["initial_hessian"]
                        actions.append({"initial_hessian": "deleted"})

        elif "premature_end_FileMan_error" in self.errors:
            # Given defaults, the first two handlers will typically be skipped.
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            elif self.qcinp.rem.get("job_type") == "opt" or self.qcinp.rem.get("job_type") == "optimization":
                if self.qcinp.rem.get("scf_guess_always", "none").lower() != "true":
                    self.qcinp.rem["scf_guess_always"] = "true"
                    actions.append({"scf_guess_always": "true"})
                else:
                    print("Don't know how to fix a FileMan error for an opt while always generating a new SCF guess!")
            elif self.qcinp.rem.get("job_type") == "freq" or self.qcinp.rem.get("job_type") == "frequency":
                self.qcinp.rem["cpscf_nseg"] = str(self.outdata["cpscf_nseg"] + 1)
                actions.append({"cpscf_nseg": str(self.outdata["cpscf_nseg"] + 1)})

        elif "hessian_eigenvalue_error" in self.errors:
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            else:
                print("Not sure how to fix hessian_eigenvalue_error if thresh is already 14!")

        elif "NLebdevPts" in self.errors:
            # this error should only be possible if resp_charges or esp_charges is set
            if self.qcinp.rem.get("resp_charges") or self.qcinp.rem.get("esp_charges"):
                # This error is caused by insufficient no. of Lebedev points on
                # the grid used to compute RESP charges
                # Increase the density of points on the Lebedev grid using the
                # esp_surface_density argument (see manual >= v5.4)
                # the default value is 500 (=0.001 Angstrom)
                # or disable RESP charges as a last resort
                if int(self.qcinp.rem.get("esp_surface_density", 500)) >= 500:
                    self.qcinp.rem["esp_surface_density"] = "250"
                    actions.append({"esp_surface_density": "250"})
                elif int(self.qcinp.rem.get("esp_surface_density", 250)) >= 250:
                    self.qcinp.rem["esp_surface_density"] = "125"
                    actions.append({"esp_surface_density": "125"})
                elif int(self.qcinp.rem.get("esp_surface_density", 125)) >= 125:
                    # switch from Lebedev mode to spherical harmonics mode
                    if self.qcinp.rem.get("resp_charges"):
                        self.qcinp.rem["resp_charges"] = "2"
                        actions.append({"resp_charges": "2"})
                    if self.qcinp.rem.get("esp_charges"):
                        self.qcinp.rem["esp_charges"] = "2"
                        actions.append({"esp_charges": "2"})
                else:
                    if self.qcinp.rem.get("resp_charges"):
                        self.qcinp.rem["resp_charges"] = "false"
                        actions.append({"resp_charges": "false"})
                    if self.qcinp.rem.get("esp_charges"):
                        self.qcinp.rem["esp_charges"] = "false"
                        actions.append({"esp_charges": "false"})
            else:
                raise RuntimeError("Not sure how to fix NLebdevPts error if resp_charges is disabled!")

        elif "failed_to_transform_coords" in self.errors:
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            if self.qcinp.rem.get("s2thresh", "14") != "16":
                self.qcinp.rem["s2thresh"] = "16"
                actions.append({"s2thresh": "16"})
            # Check for symmetry flag in rem. If not False, set to False and rerun.
            if not self.qcinp.rem.get("sym_ignore") or self.qcinp.rem.get("symmetry"):
                self.qcinp.rem["sym_ignore"] = "true"
                self.qcinp.rem["symmetry"] = "false"
                actions += ({"sym_ignore": "true"}, {"symmetry": "false"})
            else:
                print("Not sure how else to fix a failed coordinate transformation")

        elif "failed_cpscf" in self.errors:
            # For large systems, cpscf errors can often be resolved by forcing QChem to break up
            # the solving into more sections
            self.qcinp.rem["cpscf_nseg"] = str(self.outdata["cpscf_nseg"] + 1)
            actions.append({"cpscf_nseg": str(self.outdata["cpscf_nseg"] + 1)})

        elif "bad_old_nbo6_rem" in self.errors:
            # "run_nbo6" has to change to "nbo_external" in QChem 5.4.2 and later
            del self.qcinp.rem["run_nbo6"]
            self.qcinp.rem["nbo_external"] = "true"
            actions += ({"run_nbo6": "deleted"}, {"nbo_external": "true"})

        elif "bad_new_nbo_external_rem" in self.errors:
            # Have to use "run_nbo6" instead of "nbo_external" for QChem 5.4.1 or earlier
            del self.qcinp.rem["nbo_external"]
            self.qcinp.rem["run_nbo6"] = "true"
            actions += ({"nbo_external": "deleted"}, {"run_nbo6": "true"})

        elif "esp_chg_fit_error" in self.errors:
            # this error should only be possible if resp_charges or esp_charges is set
            if self.qcinp.rem.get("resp_charges") or self.qcinp.rem.get("esp_charges"):
                if self.qcinp.rem.get("resp_charges"):
                    self.qcinp.rem["resp_charges"] = "false"
                    actions.append({"resp_charges": "false"})
                if self.qcinp.rem.get("esp_charges"):
                    self.qcinp.rem["esp_charges"] = "false"
                    actions.append({"esp_charges": "false"})
            else:
                print("Not sure how to fix ESPChgFit error if resp_charges is disabled!")

        elif "probably_out_of_memory" in self.errors:
            # A frequency job that probably needs to be split into more cpscf segments
            # but did not exit gracefully
            if self.outdata["cpscf_nseg"] == 1:
                self.qcinp.rem["cpscf_nseg"] = "3"
                actions.append({"cpscf_nseg": "3"})
            else:
                self.qcinp.rem["cpscf_nseg"] = str(self.outdata["cpscf_nseg"] + 1)
                actions.append({"cpscf_nseg": str(self.outdata["cpscf_nseg"] + 1)})

        elif "gdm_neg_precon_error" in self.errors:
            if "molecule_from_last_geometry" in self.outdata:
                self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})
            else:
                print("Not sure how to fix gdm_neg_precon_error on the first SCF!")

        elif "mem_static_too_small" in self.errors:
            # mem_static should never exceed 2000 MB according to the Q-Chem manual
            self.qcinp.rem["mem_static"] = "2000"
            actions.append({"mem_static": "2000"})

        elif "mem_total_too_small" in self.errors:
            print(f"Run on a node with more memory! Current mem_total = {self.outdata['mem_total']}")
            return {"errors": self.errors, "actions": None}

        elif "basis_not_supported" in self.errors:
            print("Specify a different basis set. At least one of the atoms is not supported.")
            return {"errors": self.errors, "actions": None}

        elif "input_file_error" in self.errors:
            print("Something is wrong with the input file. Examine error message by hand.")
            return {"errors": self.errors, "actions": None}

        elif any(
            err in self.errors
            for err in ("failed_to_read_input", "read_molecule_error", "never_called_qchem", "licensing_error")
        ):
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is.
            actions.append({"rerun_job_no_changes": True})

        elif "unknown_error" in self.errors:
            if self.qcinp.rem.get("scf_guess", "none").lower() == "read":
                del self.qcinp.rem["scf_guess"]
                actions.append({"scf_guess": "deleted"})
            elif self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            else:
                print("Unknown error. Examine output and log files by hand.")
                return {"errors": self.errors, "actions": None}

        else:
            # You should never get here. If correct is being called then errors should have at least one entry,
            # in which case it should have been caught by the if/elifs above.
            print("Errors:", self.errors)
            print("Must have gotten an error which is correctly parsed but not included in the handler. FIX!!!")
            return {"errors": self.errors, "actions": None}

        if {"molecule": "molecule_from_last_geometry"} in actions and str(
            self.qcinp.rem.get("geom_opt_hessian")
        ).lower() == "read":
            del self.qcinp.rem["geom_opt_hessian"]
            actions.append({"geom_opt_hessian": "deleted"})
        if (
            {"molecule": "molecule_from_last_geometry"} in actions
            and self.outdata["version"] == "6"
            and "initial_hessian" in self.qcinp.geom_opt
        ) and str(self.qcinp.geom_opt["initial_hessian"]).lower() == "read":
            del self.qcinp.geom_opt["initial_hessian"]
            actions.append({"initial_hessian": "deleted"})

        os.replace(self._input_path, os.path.join(directory, self.input_file + ".last"))
        self.qcinp.write_file(self._input_path)
        return {"errors": self.errors, "warnings": self.warnings, "actions": actions}
