#!/usr/bin/env python

"""
This is a script to converge the geometry of a system
"""

import logging

from pymatgen.io.vasp.outputs import Vasprun

from custodian.custodian import Custodian
from custodian.vasp.handlers import (
    MeshSymmetryErrorHandler,
    NonConvergingErrorHandler,
    PotimErrorHandler,
    UnconvergedErrorHandler,
    VaspErrorHandler,
)
from custodian.vasp.jobs import VaspJob

FORMAT = "%(asctime)s %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")


def get_runs(args):
    """
    Get the runs.
    """
    vasp_command = args.command.split()
    converged = False
    job_number = 0

    while (not converged) and (job_number < args.max_relax):
        suffix = f".relax{job_number + 1}"

        if job_number == 0:
            backup = True
            # assume the initial guess is poor,
            # start with conjugate gradients
            settings = [{"dict": "INCAR", "action": {"_set": {"IBRION": 2}}}]

        else:
            backup = False
            v = Vasprun("vasprun.xml")

            if len(v.ionic_steps) == 1:
                converged = True

            if job_number < 2 and not converged:
                settings = [
                    {"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
                    {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
                ]

            # switch to RMM-DIIS once we are near the
            # local minimum (assumed after 2 runs of CG)
            else:
                settings = [
                    {"dict": "INCAR", "action": {"_set": {"ISTART": 1, "IBRION": 1}}},
                    {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}},
                ]

        job_number += 1
        yield VaspJob(
            vasp_command,
            final=converged,
            backup=backup,
            suffix=suffix,
            settings_override=settings,
        )


def do_run(args):
    """
    Perform the run.
    """
    handlers = [
        VaspErrorHandler(),
        MeshSymmetryErrorHandler(),
        UnconvergedErrorHandler(),
        NonConvergingErrorHandler(),
        PotimErrorHandler(),
    ]
    c = Custodian(handlers, get_runs(args), max_errors=10, gzipped_output=args.gzip)
    c.run()
    logging.info("Geometry optimization complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="""
    converge_geometry performs a geometry optimization. What this script will do
    is run a particular VASP relaxation repeatedly until the geometry
    is converged within the first ionic step. This is a common practice for
    converging molecular geometries in VASP, especially in situations where
    the geometry needs to be precise: such as frequency calculations.
    """,
        epilog="Author: Stephen Dacek",
    )

    parser.add_argument(
        "-c",
        "--command",
        dest="command",
        nargs="?",
        default="pvasp",
        type=str,
        help="VASP command. Defaults to pvasp. If you are using mpirun, " 'set this to something like "mpirun pvasp".',
    )

    parser.add_argument(
        "-z",
        "--gzip",
        dest="gzip",
        action="store_true",
        help="Add this option to gzip the final output. Do not gzip if you "
        "are going to perform an additional static run.",
    )

    parser.add_argument(
        "-mr",
        "--max_relaxtions",
        dest="max_relax",
        default=10,
        type=int,
        help="Maximum number of relaxations to allow",
    )

    args = parser.parse_args()
    do_run(args)
