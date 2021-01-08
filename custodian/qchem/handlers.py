# coding: utf-8

"""
This module implements new error handlers for QChem runs.
"""

import os
from pymatgen.io.qchem.inputs import QCInput
from pymatgen.io.qchem.outputs import QCOutput
from custodian.custodian import ErrorHandler
from custodian.utils import backup

__author__ = "Samuel Blau, Brandon Wood, Shyam Dwaraknath"
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
        scf_max_cycles=200,
        geom_max_cycles=200,
    ):
        """
        Initializes the error handler from a set of input and output files.

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

    def check(self):
        """
        Checks output file for errors
        """
        self.outdata = QCOutput(self.output_file).data
        self.errors = self.outdata.get("errors")
        self.warnings = self.outdata.get("warnings")
        # If we aren't out of optimization cycles, but we were in the past, reset the history
        if "out_of_opt_cycles" not in self.errors and len(self.opt_error_history) > 0:
            self.opt_error_history = []
        # If we're out of optimization cycles and we have unconnected fragments, no need to handle any errors
        if (
            "out_of_opt_cycles" in self.errors
            and self.outdata["structure_change"] == "unconnected_fragments"
        ):
            return False
        return len(self.errors) > 0

    def correct(self):
        """
        Perform corrections
        """
        backup({self.input_file, self.output_file})
        actions = []
        self.qcinp = QCInput.from_file(self.input_file)

        if "SCF_failed_to_converge" in self.errors:
            # Check number of SCF cycles. If not set or less than scf_max_cycles,
            # increase to that value and rerun. If already set, check if
            # scf_algorithm is unset or set to DIIS, in which case set to GDM.
            # Otherwise, tell user to call SCF error handler and do nothing.
            if str(self.qcinp.rem.get("max_scf_cycles")) != str(self.scf_max_cycles):
                self.qcinp.rem["max_scf_cycles"] = self.scf_max_cycles
                actions.append({"max_scf_cycles": self.scf_max_cycles})
            elif self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            elif self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                self.qcinp.rem["scf_algorithm"] = "diis_gdm"
                actions.append({"scf_algorithm": "diis_gdm"})
            elif self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis_gdm":
                self.qcinp.rem["scf_algorithm"] = "gdm"
                actions.append({"scf_algorithm": "gdm"})
            elif self.qcinp.rem.get("scf_guess_always", "none").lower() != "true":
                self.qcinp.rem["scf_guess_always"] = True
                actions.append({"scf_guess_always": True})
            else:
                print(
                    "More advanced changes may impact the SCF result. Use the SCF error handler"
                )

        elif "out_of_opt_cycles" in self.errors:
            # Check number of opt cycles. If less than geom_max_cycles, increase
            # to that value, set last geom as new starting geom and rerun.
            if str(self.qcinp.rem.get("geom_opt_max_cycles")) != str(
                self.geom_max_cycles
            ):
                self.qcinp.rem["geom_opt_max_cycles"] = self.geom_max_cycles
                actions.append({"geom_max_cycles:": self.scf_max_cycles})
                if len(self.outdata.get("energy_trajectory")) > 1:
                    self.qcinp.molecule = self.outdata.get(
                        "molecule_from_last_geometry"
                    )
                    actions.append({"molecule": "molecule_from_last_geometry"})
            elif self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            # Will need to try and implement this dmax handler below when I have more time
            # to fix the tests and the general handling procedure.
            # elif self.qcinp.rem.get("geom_opt_dmax",300) != 150:
            #     self.qcinp.rem["geom_opt_dmax"] = 150
            #     actions.append({"geom_opt_dmax": "150"})
            # If already at geom_max_cycles, thresh 14, and dmax 150, often can just get convergence
            # by restarting from the geometry of the last cycle. But we'll also save any structural
            # changes that happened along the way.
            else:
                self.opt_error_history += [self.outdata["structure_change"]]
                if len(self.opt_error_history) > 1:
                    if self.opt_error_history[-1] == "no_change":
                        # If no structural changes occured in two consecutive optimizations,
                        # and we still haven't converged, then just exit.
                        return {
                            "errors": self.errors,
                            "actions": None,
                            "opt_error_history": self.opt_error_history,
                        }
                self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})

        elif "unable_to_determine_lamda" in self.errors:
            # Set last geom as new starting geom and rerun. If no opt cycles,
            # use diff SCF strat? Diff initial guess? Change basis? Unclear.
            if len(self.outdata.get("energy_trajectory")) > 1:
                self.qcinp.molecule = self.outdata.get("molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})
            elif self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            else:
                print("Use a different initial guess? Perhaps a different basis?")

        elif "premature_end_FileMan_error" in self.errors:
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            elif self.qcinp.rem.get("scf_guess_always", "none").lower() != "true":
                self.qcinp.rem["scf_guess_always"] = True
                actions.append({"scf_guess_always": True})
            else:
                print(
                    "We're in a bad spot if we get a FileMan error while always generating a new SCF guess..."
                )

        elif "hessian_eigenvalue_error" in self.errors:
            if self.qcinp.rem.get("thresh", "10") != "14":
                self.qcinp.rem["thresh"] = "14"
                actions.append({"thresh": "14"})
            else:
                print(
                    "Not sure how to fix hessian_eigenvalue_error if thresh is already 14!"
                )

        elif "failed_to_transform_coords" in self.errors:
            # Check for symmetry flag in rem. If not False, set to False and rerun.
            # If already False, increase threshold?
            if not self.qcinp.rem.get("sym_ignore") or self.qcinp.rem.get("symmetry"):
                self.qcinp.rem["sym_ignore"] = True
                self.qcinp.rem["symmetry"] = False
                actions.append({"sym_ignore": True})
                actions.append({"symmetry": False})
            else:
                print("Perhaps increase the threshold?")

        elif "input_file_error" in self.errors:
            print(
                "Something is wrong with the input file. Examine error message by hand."
            )
            return {"errors": self.errors, "actions": None}

        elif "failed_to_read_input" in self.errors:
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is.
            actions.append({"rerun_job_no_changes": True})

        elif "read_molecule_error" in self.errors:
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is.
            actions.append({"rerun_job_no_changes": True})

        elif "never_called_qchem" in self.errors:
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is.
            actions.append({"rerun_job_no_changes": True})

        elif "licensing_error" in self.errors:
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
            print(
                "Must have gotten an error which is correctly parsed but not included in the handler. FIX!!!"
            )
            return {"errors": self.errors, "actions": None}

        if {"molecule": "molecule_from_last_geometry"} in actions and str(
            self.qcinp.rem.get("geom_opt_hessian")
        ).lower() == "read":
            del self.qcinp.rem["geom_opt_hessian"]
            actions.append({"geom_opt_hessian": "deleted"})
        os.rename(self.input_file, self.input_file + ".last")
        self.qcinp.write_file(self.input_file)
        return {"errors": self.errors, "warnings": self.warnings, "actions": actions}


class QChemSCFErrorHandler(ErrorHandler):
    """
    QChem ErrorHandler class that addresses SCF non-convergence.
    """

    is_monitor = False

    def __init__(
        self,
        input_file="mol.qin",
        output_file="mol.qout",
        rca_gdm_thresh=1.0e-3,
        scf_max_cycles=200,
    ):
        """
        Initializes the error handler from a set of input and output files.

        Args:
            input_file (str): Name of the QChem input file.
            output_file (str): Name of the QChem output file.
            rca_gdm_thresh (float): The threshold for the prior scf algorithm.
                If last deltaE is larger than the threshold try RCA_DIIS
                first, else, try DIIS_GDM first.
            scf_max_cycles (int): The max iterations to set to fix SCF failure.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.scf_max_cycles = scf_max_cycles
        self.qcinp = QCInput.from_file(self.input_file)
        self.outdata = None
        self.errors = None

    def check(self):
        """
        Checks output file for errors
        """
        self.outdata = QCOutput(self.output_file).data
        self.errors = self.outdata.get("errors")
        return len(self.errors) > 0

    def correct(self):
        """
        Corrects errors, but it hasn't been implemented yet
        """
        print("This hasn't been implemented yet!")
        return {"errors": self.errors, "actions": None}
