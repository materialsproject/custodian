#!/usr/bin/env python

"""
This module implements the main Custodian class, which manages a list of jobs
given a set of error handlers, and the abstract base classes for the
ErrorHandlers and Jobs.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyue@mit.edu"
__date__ = "May 2, 2012"

import logging
import abc
import json


class Custodian(object):
    """
    The Custodian class is the manager for a list of jobs given a list of
    error handlers. The way it works is as follows:

    1. Let's say you have defined a list of jobs as [job1, job2, job3, ...] and
       you have defined a list of possible error handlers as [err1, err2, ...]
    2. Custodian will run the jobs in the order of job1, job2, ...
    3. At the end of each individual job, Custodian will run through the list
       error handlers. If an error is detected, corrective measures are taken
       and the particular job is rerun.
    """

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
        """
        Runs the job.

        Returns:
            All errors encountered as a list of list.
            [[error_dicts for job 1], [error_dicts for job 2], ....]
        """
        all_errors = []
        for i, job in enumerate(self.jobs):
            all_errors.append(list())
            for attempt in xrange(self.max_errors):
                logging.info(
                    "Starting job no. {} ({}) attempt no. {}. Errors thus far"
                    " = {}.".format(i + 1, job.name, attempt + 1,
                                    sum(map(len, all_errors))))

                # If this is the start of the job, do the setup.
                if not all_errors[-1]:
                    job.setup()

                # Run the job.
                job.run()

                # Check for errors using the error handlers and perform
                # corrections.
                error = False
                for h in self.handlers:
                    if h.check():
                        d = h.correct()
                        logging.error(str(d))
                        all_errors[-1].append(d)
                        error = True
                        break

                #Log the corrections to a json file.
                with open("corrections.json", "w") as f:
                    logging.info("Logging corrections to corrections.json...")
                    json.dump(all_errors, f, indent=4)

                # If there are no errors detected, perform postprocessing and
                # exit.
                if not error:
                    job.postprocess()
                    break

        if sum(map(len, all_errors)) == self.max_errors:
            logging.info("Max {} errors reached. Exited"
                         .format(self.max_errors))
        else:
            logging.info("Run completed")
        return all_errors


class ErrorHandler(object):
    """
    Abstract base class defining the interface for an ErrorHandler.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def check(self):
        """
        This method is called at the end of a job. Returns a boolean value
        indicating if errors are detected.
        """
        pass

    @abc.abstractmethod
    def correct(self):
        """
        This method is called at the end of a job when an error is detected.
        It should perform any corrective measures relating to the detected
        error.

        This method should return a JSON serializable dict that describes
        the errors and actions taken. E.g.
        {"errors": list_of_errors, "actions": list_of_actions_taken}
        """
        pass


class Job(object):
    """
    Abstract base class defining the interface for a Job.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def setup(self):
        """
        This method is run before the start of a job. Allows for some
        pre-processing.
        """
        pass

    @abc.abstractmethod
    def run(self):
        """
        This method perform the actual work for the job.
        """
        pass

    @abc.abstractmethod
    def postprocess(self):
        """
        This method is called at the end of a job, *after* error detection.
        This allows post-processing, such as cleanup, analysis of results,
        etc.
        """
        pass

    @abc.abstractproperty
    def name(self):
        """
        A nice string name for the job.
        """
        pass
