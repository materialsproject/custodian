#!/usr/bin/env python

'''
Created on May 2, 2012
'''

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "May 2, 2012"

import logging
import os
import tarfile


class Custodian(object):

    def __init__(self, handlers, jobs, max_errors=1):
        """
        Args:
            handlers:
                Error handlers. In order of priority of fixing.
            jobs:
                List of Jobs. Allow for multistep jobs. E.g., give it two
                BasicVaspJobs and you effectively have a aflow
                double-relaxation.
            max_errors:
                Maximum number of errors allowed before exiting.
        """
        self.max_errors = max_errors
        self.jobs = jobs
        self.handlers = handlers

    def run(self):
        total_errors = 0
        for i, job in enumerate(self.jobs):
            attempt = 0
            while total_errors < self.max_errors:
                logging.info("Starting job no. {} ({}) attempt no. {}. Errors thus far = {}.".format(i + 1, job.name, attempt + 1, total_errors))
                job.setup()
                job.run()
                error = False
                for h in self.handlers:
                    if h.check():
                        logging.error(str(h))
                        self.backup(i, attempt)
                        h.correct()
                        total_errors += 1
                        attempt += 1
                        error = True
                        break
                job.postprocess()
                if not error:
                    break
        if total_errors == self.max_errors:
            logging.info("Max {} errors reached. Exited".format(total_errors))
        else:
            logging.info("Run completed")

    def backup(self, job_no, attempt_no):
        filename = "job_{}_attempt_{}.tar.gz".format(job_no + 1,
                                                     attempt_no + 1)
        logging.info("Backing up run to {}.".format(filename))
        tar = tarfile.open(filename, "w:gz")
        for f in os.listdir("."):
            tar.add(f)
        tar.close()

