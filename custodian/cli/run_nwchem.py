"""Basic script to run nwchem job."""

import logging

from custodian.custodian import Custodian
from custodian.nwchem.handlers import NwchemErrorHandler
from custodian.nwchem.jobs import NwchemJob


def do_run(args):
    """Do the run."""
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, filename="run.log")
    job = NwchemJob(
        nwchem_cmd=args.command.split(),
        input_file=args.infile,
        output_file=args.outfile,
    )
    c = Custodian(
        [NwchemErrorHandler(output_filename=args.outfile)],
        [job],
        max_errors=5,
        scratch_dir=args.scratch,
        gzipped_output=args.gzipped,
        checkpoint=True,
    )
    c.run()


def main():
    """Main method."""
    import argparse

    parser = argparse.ArgumentParser(
        description="""
    run_nwchem is a master script to perform various kinds of Nwchem runs.
    """,
        epilog="""Author: Shyue Ping Ong""",
    )

    parser.add_argument(
        "-c",
        "--command",
        dest="command",
        nargs="?",
        default="nwchem",
        type=str,
        help="Nwchem command. Defaults to nwchem. If you are using mpirun, "
        'set this to something like "mpirun nwchem".',
    )

    parser.add_argument(
        "-s",
        "--scratch",
        dest="scratch",
        nargs="?",
        default=None,
        type=str,
        help="Scratch directory to perform run in. Specify the root scratch "
        "directory as the code will automatically create a temporary "
        "subdirectory to run the job.",
    )

    parser.add_argument(
        "-i",
        "--infile",
        dest="infile",
        nargs="?",
        default="mol.nw",
        type=str,
        help="Input filename.",
    )

    parser.add_argument(
        "-o",
        "--output",
        dest="outfile",
        nargs="?",
        default="mol.nwout",
        type=str,
        help="Output filename.",
    )

    parser.add_argument(
        "-z",
        "--gzip",
        dest="gzip",
        action="store_true",
        help="Add this option to gzip the final output. Do not gzip if you "
        "are going to perform an additional static run.",
    )

    args = parser.parse_args()
    do_run(args)


if __name__ == "__main__":
    main()
