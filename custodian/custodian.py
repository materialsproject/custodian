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
import subprocess
import time
import abc


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
        self.parallel_handlers = filter(lambda x: x.run_parallel, handlers)

    def run(self):
        total_errors = 0
        for i, job in enumerate(self.jobs):
            error = False
            for attempt in xrange(self.max_errors):
                logging.info("Starting job no. {} ({}) attempt no. {}. Errors"
                             " thus far = {}.".format(i + 1, job.name,
                                                      attempt + 1,
                                                      total_errors))
                if not error:
                    job.setup()
                
                p = job.run()
                error = False
                
                if isinstance(p, subprocess.Popen):
                    if self.parallel_handlers:
                        #checks that the process is still alive every 10s
                        #checks for errors hourly
                        n = 0
                        while True:
                            n += 1
                            time.sleep(10)
                            if p.poll() is not None:
                                break
                            if not n % 360 == 0:
                                continue
                            for h in self.parallel_handlers:
                                if h.check():
                                    p.terminate()
                                    break
                    else:
                        p.wait()
                
                for h in self.handlers:
                    if h.check():
                        logging.error(str(h))
                        h.correct()
                        total_errors += 1
                        error = True
                        break
                if not error:
                    job.postprocess()
                    break
        if total_errors == self.max_errors:
            logging.info("Max {} errors reached. Exited".format(total_errors))
        else:
            logging.info("Run completed")


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
        """
        pass
    
    def run_parallel(self):
        """
        This property determines whether the error handler should be run parallel
        to the job. If the handler notices an error, the job will be sent a 
        termination signal.
        """
        return False


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
        This method perform the actual work for the job. If parallel error checking
        is desired, this must return a Popen process
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
