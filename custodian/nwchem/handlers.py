#!/usr/bin/env python

"""
TODO: Change the module doc.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "5/20/13"

import shutil

from custodian.custodian import ErrorHandler
from pymatgen.serializers.json_coders import MSONable
from pymatgen.io.nwchemio import NwOutput


class NwchemErrorHandler(ErrorHandler, MSONable):
    """
    Error handler for Gaussian Jobs.
    """

    def __init__(self, output_filename="gau.out"):
        self.output_filename = output_filename

    def check(self):
        out = NwOutput(self.output_filename)
        self.errors = []
        self.input_file = out.job_info['input']
        if out.data[-1]["has_error"]:
            self.errors.extend(out.data[-1]["errors"])
        return len(self.errors) > 0

    def correct(self):
        actions = []
        for e in self.errors:
            if e == "autoz error":
                #Hackish solution for autoz error.
                with open("temp.nw", "w") as fout, \
                        open(self.input_file) as fin:
                    for l in fin:
                        if l.lower().strip().startswith("geometry"):
                            fout.write("{} noautoz\n".format(l.strip()))
                        else:
                            fout.write(l)
                shutil.move("temp.nw", self.input_file)
                actions.append("Set noautoz to geometry")
            else:
                # For unimplemented errors, this should just cause the job to
                # die.
                return {"errors": self.errors, "actions": None}
        return {"errors": self.errors, "actions": actions}

    @property
    def is_monitor(self):
        return False

    def __str__(self):
        return "NwchemErrorHandler"

    @property
    def to_dict(self):
        return {"@module": self.__class__.__module__,
                "@class": self.__class__.__name__,
                "output_filename": self.output_filename}

    @classmethod
    def from_dict(cls, d):
        return cls(d["output_filename"])

