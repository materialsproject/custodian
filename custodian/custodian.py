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
from abc import ABCMeta, abstractmethod, abstractproperty
import json


class Custodian(object):
    """
    The Custodian class is the manager for a list of jobs given a list of
    error handlers. The way it works is as follows:

    1. Let's say you have defined a list of jobs as [job1, job2, job3, ...] and
       you have defined a list of possible error handlers as [err1, err2, ...]
    2. Custodian will run the jobs in the order of job1, job2, ... During each
       job, custodian will monitor for errors using the handlers that have
       is_monitor == True. If an error is detected, corrective measures are
       taken and the particular job is rerun.
    3. At the end of each individual job, Custodian will run through the list
       error handlers that have is_monitor == False. If an error is detected,
       corrective measures are taken and the particular job is rerun.

    .. attribute: max_errors

        Maximum number of errors allowed.

    .. attribute: handlers

        Error handlers that are not Monitors.

    .. attribute: monitors

        Error handlers that are Monitors, i.e., handlers that monitors a job
        as it is being run.

    .. attribute: polling_time_step

        The length of time in seconds between steps in which a job is
        checked for completion.

    .. attribute: monitor_freq

        The number of polling steps before monitoring occurs. For example,
        if you have a polling_time_step of 10seconds and a monitor_freq of
        30, this means that Custodian uses the monitors to check for errors
        every 30 x 10 = 300 seconds, i.e., 5 minutes.
    """

    def __init__(self, handlers, jobs, max_errors=1, polling_time_step=10,
                 monitor_freq=30):
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
            polling_time_step:
                The length of time in seconds between steps in which a
                job is checked for completion. Defaults to 10 seconds.
            monitor_freq:
                The number of polling steps before monitoring occurs. For
                example, if you have a polling_time_step of 10seconds and a
                monitor_freq of 30, this means that Custodian uses the
                monitors to check for errors every 30 x 10 = 300 seconds,
                i.e., 5 minutes.
        """
        self.max_errors = max_errors
        self.jobs = jobs
        self.handlers = filter(lambda x: not x.is_monitor, handlers)
        self.monitors = filter(lambda x: x.is_monitor, handlers)
        self.polling_time_step = polling_time_step
        self.monitor_freq = monitor_freq

    def run(self):
        """
        Runs the job.

        Returns:
            All errors encountered as a list of list.
            [[error_dicts for job 1], [error_dicts for job 2], ....]
        """
        run_log = []
        total_errors = 0
        for i, job in enumerate(self.jobs):
            run_log.append({"job": job.to_dict, "corrections": []})
            for attempt in xrange(self.max_errors):
                logging.info(
                    "Starting job no. {} ({}) attempt no. {}. Errors thus far"
                    " = {}.".format(i + 1, job.name, attempt + 1, total_errors))

                # If this is the start of the job, do the setup.
                if not run_log[-1]["corrections"]:
                    job.setup()

                p = job.run()
                # Check for errors using the error handlers and perform
                # corrections.
                error = False

                # While the job is running, we use the handlers that are
                # monitors to monitor the job.
                if isinstance(p, subprocess.Popen):
                    if self.monitors:
                        n = 0
                        while True:
                            n += 1
                            time.sleep(self.polling_time_step)
                            if p.poll() is not None:
                                break
                            if n % self.monitor_freq == 0:
                                for h in self.monitors:
                                    if h.check():
                                        p.terminate()
                                        d = h.correct()
                                        logging.error(str(d))
                                        run_log[-1]["corrections"].append(d)
                                        error = True
                                        break
                    else:
                        p.wait()

                # If there are no errors *during* the run, we now check for
                # errors *after* the run using handlers that are not monitors.
                if not error:
                    for h in self.handlers:
                        if h.check():
                            total_errors += 1
                            d = h.correct()
                            logging.error(str(d))
                            run_log[-1]["corrections"].append(d)
                            error = True
                            break

                #Log the corrections to a json file.
                with open("custodian.json", "w") as f:
                    logging.info("Logging to custodian.json...")
                    json.dump(run_log, f, indent=4)

                # If there are no errors detected, perform postprocessing and
                # exit.
                if not error:
                    job.postprocess()
                    break

        if total_errors == self.max_errors:
            logging.info("Max {} errors reached. Exited"
                         .format(self.max_errors))
        else:
            logging.info("Run completed")
        return run_log


class ErrorHandler(object):
    """
    Abstract base class defining the interface for an ErrorHandler.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def check(self):
        """
        This method is called at the end of a job. Returns a boolean value
        indicating if errors are detected.
        """
        pass

    @abstractmethod
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

    @abstractproperty
    def is_monitor(self):
        """
        This property indicates whether the error handler is a monitor,
        i.e., a handler that monitors a job as it is running. If a
        monitor-type handler notices an error, the job will be sent a
        termination signal, the error is then corrected,
        and then the job is restarted. This is useful for catching errors
        that occur early in the run but do not cause immediate failure.
        """
        return False

    @abstractproperty
    def to_dict(self):
        """
        This method should return a JSON serializable dict describing the
        ErrorHandler, and can be deserialized using the from_dict static
        method.
        """
        pass

    @staticmethod
    def from_dict(d):
        """
        This simply raises a NotImplementedError to force subclasses to
        implement this static method. Abstract static methods are not
        implemented until Python 3+.
        """
        raise NotImplementedError("ErrorHandler objects must implement a "
                                  "from_dict static method.")


class Job(object):
    """
    Abstract base class defining the interface for a Job.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def setup(self):
        """
        This method is run before the start of a job. Allows for some
        pre-processing.
        """
        pass

    @abstractmethod
    def run(self):
        """
        This method perform the actual work for the job. If parallel error
        checking is desired, this must return a Popen process.
        """
        pass

    @abstractmethod
    def postprocess(self):
        """
        This method is called at the end of a job, *after* error detection.
        This allows post-processing, such as cleanup, analysis of results,
        etc.
        """
        pass

    @abstractproperty
    def name(self):
        """
        A nice string name for the job.
        """
        pass

    @abstractproperty
    def to_dict(self):
        """
        This method should return a JSON serializable dict describing the
        Job, and can be deserialized using the from_dict static
        method.
        """
        pass

    @staticmethod
    def from_dict(d):
        """
        This simply raises a NotImplementedError to force subclasses to
        implement this static method. Abstract static methods are not
        implemented until Python 3+.
        """
        raise NotImplementedError("Job objects must implement a from_dict"
                                  "static method.")
