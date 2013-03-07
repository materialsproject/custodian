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
from custodian.vasp.handlers import VaspErrorHandler, \
    UnconvergedErrorHandler, PoscarErrorHandler
from custodian.vasp.jobs import VaspJob


def double_relax(args):
    FORMAT = '%(asctime)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    handlers = [VaspErrorHandler(), UnconvergedErrorHandler(),
                PoscarErrorHandler()]
    jobs = VaspJob.double_relaxation_run(args.command.split())
    c = Custodian(handlers, jobs, max_errors=10)
    c.run()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="""
    double_relaxation.py performs a double relaxation VASP run.""",
    epilog="""
    Author: Shyue Ping Ong
    Version: {}
    Last updated: {}""".format(__version__, __date__))

    parser.add_argument(
        "-c", "--command", dest="command", nargs="?",
        default="pvasp", type=str,
        help="VASP command. Defaults to pvasp. If you are using mpirun, "
             "set this to something like \"mpirun pvasp\".")
    double_relax(parser.parse_args())