#!/usr/bin/env python

"""
Basic script to run gaussian job inside Custodian (a simple copy of run_nwchem from Custodian
"""

from __future__ import division

import logging

from custodian.custodian import Custodian
from mygaussianmodule.gaussian_fireworks.mygaussianhandlers import GaussianErrorHandler
from mygaussianmodule.gaussian_fireworks.mygaussianjobs import GaussianJob



def do_run(args):
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO,
                        filename=args.outfile + ".run.log")
    job = GaussianJob(gaussian_cmd=args.command,
                    input_file=args.infile,
                    output_file=args.outfile)
    c = Custodian([GaussianErrorHandler(output_filename=args.outfile)], [job],
                  max_errors=5, scratch_dir=args.scratch,
                  gzipped_output=False, checkpoint=True)
    c.run()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="""
    run_gaussian is a master script to perform various kinds of Gaussian runs.
    """)

    parser.add_argument(
        "-c", "--command", dest="command", nargs="?",
        default="g09", type=str,
        help="Gaussian command. Defaults to Gaussian")

    parser.add_argument(
        "-s", "--scratch", dest="scratch", nargs="?",
        default=None, type=str,
        help="Scratch directory to perform run in. Specify the root scratch "
             "directory as the code will automatically create a temporary "
             "subdirectory to run the job.")

    parser.add_argument(
        "-i", "--infile", dest="infile", nargs="?", default="mol.gau",
        type=str, help="Input filename.")

    parser.add_argument(
        "-o", "--output", dest="outfile", nargs="?", default="mol.log",
        type=str, help="Output filename."
    )

    parser.add_argument(
        "-z", "--gzip", dest="gzip", action="store_true",
        help="Add this option to gzip the final output. Do not gzip if you "
             "are going to perform an additional static run."
    )

    args = parser.parse_args()
    do_run(args)