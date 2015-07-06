# coding: utf-8

__author__ = 'ndardenne'

import os

from custodian.custodian import ErrorHandler
from custodian.utils import backup
from custodian.ansible.interpreter import Modder

from pymatgen.io.gaussianio import GaussianOutput, GaussianInput



class GaussianErrorHandler(ErrorHandler):
    """
    Errors handler for Gaussian jobs to be used inside Custodian
            
    """

    is_monitor = False

    def __init__(self, output_filename="mol.log"):
        """
        Initializes with an output file name.

        Args:
            output_filename (str): This is the file where the stdout for gaussian
                is being redirected. The error messages that are checked are
                present in the stdout. Defaults to "mol.log"`.
        """
        self.output_filename = output_filename

    def check(self):
        # Checks output file for errors (already implemented in the GaussianOutput)
        out = GaussianOutput(self.output_filename)
        self.output = out
        self.errors = out.errors
        fN, fE = os.path.splitext(self.output_filename)
        self.input_file_name = fN+'.gau'
        return len(self.errors) > 0

    def correct(self):
        backup(["*.log"])
        actions = []
        gaui = GaussianInput.from_file(self.input_file_name)

        for error in self.errors:
            if error == "NtrErr":
                mol = self.output.final_structure # take the final structure from the previous run
                route_parameters = gaui.route_parameters
                route_parameters.update({"Guess":"TCheck","Geom": "Checkpoint"})
                empty_dict = dict()

                action = {"_set":
                              {"route_parameters": route_parameters,
                               "molecule": empty_dict}
                            }
                actions.append(action)
            elif error == "Optimization error_new":
                mol = self.output.final_structure # take the final structure from the previous run
                route_parameters = gaui.route_parameters
                route_parameters.update({"Guess":"TCheck","Opt": "CalcFC"})

                action = {"_set":
                              {"route_parameters": route_parameters,
                               "molecule": mol.as_dict()}
                            }
                actions.append(action)
            elif error == "FormBX problem":
                mol = self.output.final_structure # take the final structure from the previous run
                route_parameters = gaui.route_parameters
                route_parameters.update({"Guess":"TCheck","Geom":"cartesian"})

                action = {"_set":
                              {"route_parameters": route_parameters,
                               "molecule": mol.as_dict()}
                            }
                actions.append(action)
            elif error == "SCF convergence error":
                mol = self.output.final_structure # take the final structure from the previous run
                route_parameters = gaui.route_parameters
                route_parameters.update({"Guess":"TCheck","SCF":"QC"})

                action = {"_set":
                              {"route_parameters": route_parameters,
                               "molecule": mol.as_dict()}
                            }
                actions.append(action)
            else:
                # For unimplemented errors, this should just cause the job to
                # die.
                return {"errors": self.errors, "actions": None}


        m = Modder()
        for action in actions:
            gaui = m.modify_object(action, gaui)
        gaui.write_file(self.input_file_name)
        return {"errors": self.errors, "actions": actions}


    def __str__(self):
        return "GaussianErrorHandler"

