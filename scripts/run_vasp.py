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


def relaxation_run(args):
    FORMAT = '%(asctime)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    handlers = [VaspErrorHandler(), UnconvergedErrorHandler(),
                PoscarErrorHandler()]
    vasp_command = args.command.split()
    jobs = []
    if args.repeat == 1:
        jobs.append(VaspJob(vasp_command, final=True, suffix="", gzipped=True))
    elif args.repeat > 1:
        jobs.append(VaspJob(vasp_command, final=False, suffix=".relax1"))
        for i in xrange(1, args.repeat):
            if i != args.repeat - 1:
                jobs.append(
                    VaspJob(
                        vasp_command, final=False,
                        suffix=".relax{}".format(i + 1),
                        settings_override=[
                            {"dict": "INCAR",
                             "action": {"_set": {"ISTART": 1}}},
                            {"filename": "CONTCAR",
                             "action": {"_file_copy": {"dest": "POSCAR"}}}]))
            else:
                jobs.append(
                    VaspJob(
                        vasp_command, final=True, backup=False,
                        suffix=".relax{}".format(i + 1), gzipped=True,
                        settings_override=[
                            {"dict": "INCAR",
                             "action": {"_set": {"ISTART": 1}}},
                            {"filename": "CONTCAR",
                             "action": {"_file_copy": {"dest": "POSCAR"}}}]))

    c = Custodian(handlers, jobs, max_errors=10)
    c.run()


def static_run(args):
    FORMAT = '%(asctime)s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    handlers = [VaspErrorHandler()]
    vasp_command = args.command.split()
    jobs = [VaspJob(
        vasp_command, final=True,
        suffix=".static",
        settings_override=[
            {"dict": "INCAR",
             "action": {"_set": {"ISTART": 1, "NSW": 0}}},
            {"filename": "CONTCAR",
             "action": {"_file_copy": {"dest": "POSCAR"}}}])]
    c = Custodian(handlers, jobs, max_errors=10)
    c.run()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="""
    run_vasp.py is a master script to perform various kinds of VASP runs.
    """,
    epilog="""
    Author: Shyue Ping Ong
    Version: {}
    Last updated: {}""".format(__version__, __date__))

    subparsers = parser.add_subparsers()

    prelax = subparsers.add_parser("relax", help="Do relaxation run.")

    prelax.add_argument(
        "-c", "--command", dest="command", nargs="?",
        default="pvasp", type=str,
        help="VASP command. Defaults to pvasp. If you are using mpirun, "
             "set this to something like \"mpirun pvasp\".")

    prelax.add_argument(
        "-r", "--repeat", dest="repeat", default=2, type=int,
        help="Number of repeats for the vasprun. Defaults to 2 for a double "
             "relaxation.")

    prelax.set_defaults(func=relaxation_run)

    pstatic = subparsers.add_parser("static", help="Do a static run.")

    pstatic.add_argument(
        "-c", "--command", dest="command", nargs="?",
        default="pvasp", type=str,
        help="VASP command. Defaults to pvasp. If you are using mpirun, "
             "set this to something like \"mpirun pvasp\".")

    pstatic.set_defaults(func=static_run)

    args = parser.parse_args()
    args.func(args)