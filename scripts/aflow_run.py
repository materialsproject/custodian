#!/usr/bin/env python

"""
TODO: Change the module doc.
"""

from __future__ import division

__author__ = "shyuepingong"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__status__ = "Beta"
__date__ = "2/4/13"

import logging

from custodian.custodian import Custodian
from custodian.vasp.handlers import VaspErrorHandler, UnconvergedErrorHandler, PoscarErrorHandler
from custodian.vasp.jobs import VaspJob

def aflow_run():
    #An example of an aflow run.

    FORMAT = '%(asctime)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    handlers = [VaspErrorHandler(), UnconvergedErrorHandler(),
                PoscarErrorHandler()]
    vasp_command = ["mpirun", "/share/apps/bin/pvasp.5.2.11"]
    jobs = [VaspJob(vasp_command, final=False, suffix=".relax1"),
            VaspJob(vasp_command, final=True, backup=False, suffix=".relax2",
                    gzipped=True,
                    settings_override=[{"dict": "INCAR",
                                        "action": {"_set": {"ISTART": 1}}},
                                       {"filename": "CONTCAR",
                                        "action": {"_file_copy": "POSCAR"}}])]
    c = Custodian(handlers, jobs, max_errors=10)
    c.run()

if __name__ == "__main__":
    aflow_run()