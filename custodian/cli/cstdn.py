#!/usr/bin/env python
# Copyright (c) Materials Virtual Lab.
# Distributed under the terms of the BSD License.

"""
A yaml based Custodian job runner. Allows for multi-step jobs with modifications along the way.
"""

import argparse
import logging
import sys

from monty.serialization import loadfn

from custodian.custodian import Custodian

example_yaml = """
# This is an example of a Custodian yaml spec file. It shows how you can specify
# a double relaxation followed by a static calculation. Minor modifications
# would allow very customizable calculations, though this is obviously not meant
# for highly complex workflows. For those, you will need to code and usage of
# FireWorks is highly recommended.


# Specifies a list of jobs to run.
# Each job is specified by a `jb: <full class path>` with parameters specified
# via the params dict.

jobs:
- jb: custodian.vasp.jobs.VaspJob
  params:
    final: False
    suffix: .relax1
- jb: custodian.vasp.jobs.VaspJob
  params:
    final: False
    suffix: .relax2
    settings_override:
    - {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
- jb: custodian.vasp.jobs.VaspJob
  params:
    final: True
    suffix: .static3
    settings_override:
    - {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}
    - {"dict": "INCAR", "action": {"_set": {"NSW": 0}}}


# This key specifies parameters common to all jobs.
# Keys starting with $ are expanded to the environmental values.
# The example below means the parameter vasp_cmd is set to the value with
# $PBS_NODEFILE expanded.

jobs_common_params:
  $vasp_cmd: ["mpirun", "-machinefile", "$PBS_NODEFILE", "-np", "24", "vasp"]


# Specifies a list of error handlers in the same format as jobs.
handlers:
- hdlr: custodian.vasp.handlers.VaspErrorHandler
- hdlr: custodian.vasp.handlers.AliasingErrorHandler
- hdlr: custodian.vasp.handlers.MeshSymmetryErrorHandler


# Specifies a list of error handlers in the same format as jobs.
validators:
- vldr: custodian.vasp.validators.VasprunXMLValidator


# This sets all custodian running parameters.
custodian_params:
  max_errors: 10
  scratch_dir: /tmp
  gzipped_output: True
  checkpoint: True
"""


def run(args):
    """
    Perform a single run.
    """
    FORMAT = "%(asctime)s %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO, filename="run.log")
    logging.info(f"Spec file is {args.spec_file}")
    d = loadfn(args.spec_file[0])
    c = Custodian.from_spec(d)
    c.run()


def print_example(args):
    """
    Print the example_yaml.
    """
    print(example_yaml)


def main():
    """
    Main method
    """
    parser = argparse.ArgumentParser(
        description="""
    cstdn is a convenient script to run custodian style jobs using a
    simple YAML spec.""",
        epilog="""Author: Shyue Ping Ong""",
    )

    subparsers = parser.add_subparsers()

    prun = subparsers.add_parser("run", help="Run custodian.")
    prun.add_argument("spec_file", metavar="spec_file", type=str, nargs=1, help="YAML/JSON spec file.")
    prun.set_defaults(func=run)

    prun = subparsers.add_parser(
        "example",
        help="Print examples. Right now, there is only one example for VASP double relaxation.",
    )
    prun.set_defaults(func=print_example)

    args = parser.parse_args()

    try:
        getattr(args, "func")
    except AttributeError:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
