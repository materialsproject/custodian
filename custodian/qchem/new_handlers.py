# coding: utf-8

from __future__ import unicode_literals, division

# This module implements new error handlers for QChem runs.

import os
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
__credits__ = "Xiaohui Qu"


class QChemErrorHandler(ErrorHandler):
    """
    Master QChemErrorHandler class that handles a number of common errors
    that occur during QChem runs.
    """

    is_monitor = False

    def __init__(self,
                 input_file="mol.qin",
                 output_file="mol.qout",
                 scf_max_cycles=200,
                 geom_max_cycles=200):
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
        self.qcinp = QCInput.from_file(self.input_file)
        self.outdata = None
        self.errors = []

    def check(self):
        # Checks output file for errors.
        self.outdata = QCOutput(self.output_file).data
        self.errors = self.outdata.get("errors")
        return len(self.errors) > 0

    def correct(self):
        backup({self.input_file, self.output_file})
        actions = []

        if "SCF_failed_to_converge" in self.errors:
            # Check number of SCF cycles. If not set or less than scf_max_cycles,
            # increase to that value and rerun. If already set, check if
            # scf_algorithm is unset or set to DIIS, in which case set to RCA-DIIS.
            # Otherwise, tell user to call SCF error handler and do nothing.
            if self.qcinp.rem.get("max_scf_cycles") != str(
                    self.scf_max_cycles):
                self.qcinp.rem["max_scf_cycles"] = self.scf_max_cycles
                actions.append({"max_scf_cycles": self.scf_max_cycles})
            elif self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                self.qcinp.rem["scf_algorithm"] = "rca_diis"
                actions.append({"scf_algorithm": "rca_diis"})
                if self.qcinp.rem.get("gen_scfman"):
                    self.qcinp.rem["gen_scfman"] = False
                    actions.append({"gen_scfman": False})
            else:
                print(
                    "More advanced changes may impact the SCF result. Use the SCF error handler"
                )

        elif "out_of_opt_cycles" in self.errors:
            # Check number of opt cycles. If less than geom_max_cycles, increase
            # to that value, set last geom as new starting geom and rerun.
            if self.qcinp.rem.get(
                    "geom_opt_max_cycles") != self.geom_max_cycles:
                self.qcinp.rem["geom_opt_max_cycles"] = self.geom_max_cycles
                actions.append({"geom_max_cycles:": self.scf_max_cycles})
                if len(self.outdata.get("energy_trajectory")) > 1:
                    if self.qcinp.molecule.spin_multiplicity != self.outdata.get(
                            "molecule_from_last_geometry").spin_multiplicity:
                        raise AssertionError('Multiplicities should match!')
                    if self.qcinp.molecule.charge != self.outdata.get(
                            "molecule_from_last_geometry").charge:
                        raise AssertionError('Charges should match!')
                    self.qcinp.molecule = self.outdata.get(
                        "molecule_from_last_geometry")
                    actions.append({"molecule": "molecule_from_last_geometry"})
            else:
                print(
                    "How do I get the geometry optimization converged when already at the maximum number of cycles?"
                )

        elif "unable_to_determine_lamda" in self.errors:
            # Set last geom as new starting geom and rerun. If no opt cycles,
            # use diff SCF strat? Diff initial guess? Change basis?
            if len(self.outdata.get("energy_trajectory")) > 1:
                if self.qcinp.molecule.spin_multiplicity != self.outdata.get(
                        "molecule_from_last_geometry").spin_multiplicity:
                    raise AssertionError('Multiplicities should match!')
                if self.qcinp.molecule.charge != self.outdata.get(
                        "molecule_from_last_geometry").charge:
                    raise AssertionError('Charges should match!')
                self.qcinp.molecule = self.outdata.get(
                    "molecule_from_last_geometry")
                actions.append({"molecule": "molecule_from_last_geometry"})
            elif self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                self.qcinp.rem["scf_algorithm"] = "rca_diis"
                actions.append({"scf_algorithm": "rca_diis"})
                if self.qcinp.rem.get("gen_scfman"):
                    self.qcinp.rem["gen_scfman"] = False
                    actions.append({"gen_scfman": False})
            else:
                print(
                    "Use a different initial guess? Perhaps a different basis?"
                )

        elif "linear_dependent_basis" in self.errors:
            # DIIS -> RCA_DIIS. If already RCA_DIIS, change basis?
            if self.qcinp.rem.get("scf_algorithm", "diis").lower() == "diis":
                self.qcinp.rem["scf_algorithm"] = "rca_diis"
                actions.append({"scf_algorithm": "rca_diis"})
                if self.qcinp.rem.get("gen_scfman"):
                    self.qcinp.rem["gen_scfman"] = False
                    actions.append({"gen_scfman": False})
            else:
                print("Perhaps use a better basis?")

        elif "failed_to_transform_coords" in self.errors:
            # Check for symmetry flag in rem. If not False, set to False and rerun.
            # If already False, increase threshold?
            if not self.qcinp.rem.get("sym_ignore") or self.qcinp.rem.get(
                    "symmetry"):
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
            actions.append({"rerun job as-is"})

        elif "IO_error" in self.errors:
            # Almost certainly just a temporary problem that will not be encountered again. Rerun job as-is.
            actions.append({"rerun job as-is"})

        elif "unknown_error" in self.errors:
            print("Examine error message by hand.")
            return {"errors": self.errors, "actions": None}

        else:
            # You should never get here. If correct is being called then errors should have at least one entry,
            # in which case it should have been caught by the if/elifs above.
            print(
                "If you get this message, something has gone terribly wrong!")
            return {"errors": self.errors, "actions": None}

        os.rename(self.input_file, self.input_file + ".last")
        self.qcinp.write_file(self.input_file)
        return {"errors": self.errors, "actions": actions}


class QChemSCFErrorHandler(ErrorHandler):
    """
    QChem ErrorHandler class that addresses SCF non-convergence.
    """

    is_monitor = False

    def __init__(self,
                 input_file="mol.qin",
                 output_file="mol.qout",
                 rca_gdm_thresh=1.0E-3,
                 scf_max_cycles=200):
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
        print("This hasn't been implemented yet!")
        return {"errors": self.errors, "actions": None}
