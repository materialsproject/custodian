#!/usr/bin/env python

"""
This module implements the main Custodian class, which manages a list of jobs
given a set of error handlers, the abstract base classes for the
ErrorHandlers and Jobs.
"""

from __future__ import division

__author__ = "Shyue Ping Ong, William Davidson Richards"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__date__ = "May 3, 2013"

import logging
import inspect
import subprocess
import datetime
import time
import json
from glob import glob
import tarfile
import os
import shutil
from abc import ABCMeta, abstractmethod
from monty.tempfile import ScratchDir
from monty.shutil import gzip_dir

pjoin = os.path.join


logger = logging.getLogger(__name__)


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

        All error handlers (including monitors). All error handlers are used
        to check for errors at the end of a run.

    .. attribute: monitors

        Error handlers that are Monitors, i.e., handlers that monitors a job
        as it is being run.

    .. attribute: polling_time_step

        The length of time in seconds between steps in which a job is
        checked for completion.

    .. attribute: monitor_freq

        The number of polling steps before monitoring occurs. For example,
        if you have a polling_time_step of 10 seconds and a monitor_freq of
        30, this means that Custodian uses the monitors to check for errors
        every 30 x 10 = 300 seconds, i.e., 5 minutes.
    """
    LOG_FILE = "custodian.json"

    def __init__(self, handlers, jobs, max_errors=1, polling_time_step=10,
                 monitor_freq=30, log_file="custodian.json",
                 skip_over_errors=False, scratch_dir=None,
                 gzipped_output=False, checkpoint=False):
        """
        Initializes a Custodian from a list of jobs and error handler.s

        Args:
            handlers ([ErrorHandler]): Error handlers. In order of priority of
                fixing.
            jobs ([Job]): List of Jobs to be run sequentially.
            max_errors (int): Maximum number of errors allowed before exiting.
                Defaults to 1.
            polling_time_step (int): The length of time in seconds between
                steps in which a job is checked for completion. Defaults to
                10 secs.
            monitor_freq (int): The number of polling steps before monitoring
                occurs. For example, if you have a polling_time_step of 10
                seconds and a monitor_freq of 30, this means that Custodian
                uses the monitors to check for errors every 30 x 10 = 300
                seconds, i.e., 5 minutes.
            log_file (str): Deprecated. Custodian now always logs to a
                custodian.json file.
            skip_over_errors (bool): If set to True, custodian will skip over
                error handlers that failed (raised an Exception of some sort).
                Otherwise, custodian will simply exit on unrecoverable errors.
                The former will lead to potentially more robust performance,
                but may make it difficult to improve handlers. The latter
                will allow one to catch potentially bad error handler
                implementations. Defaults to False.
            scratch_dir (str): If this is set, any files in the current
                directory are copied to a temporary directory in a scratch
                space first before any jobs are performed, and moved back to
                the current directory upon completion of all jobs. This is
                useful in some setups where a scratch partition has much
                faster IO. To use this, set scratch_dir=root of directory you
                want to use for runs. There is no need to provide unique
                directory names; we will use python's tempfile creation
                mechanisms. A symbolic link is created during the course of
                the run in the working directory called "scratch_link" as
                users may want to sometimes check the output during the
                course of a run. If this is None (the default), the run is
                performed in the current working directory.
            gzipped_output (bool): Whether to gzip the final output to save
                space. Defaults to False.
            checkpoint (bool):  Whether to checkpoint after each successful Job.
                Checkpoints are stored as custodian.chk.#.tar.gz files. Defaults
                to False.
        """
        self.max_errors = max_errors
        self.jobs = jobs
        self.handlers = handlers
        self.monitors = filter(lambda x: x.is_monitor, handlers)
        self.polling_time_step = polling_time_step
        self.monitor_freq = monitor_freq
        self.skip_over_errors = skip_over_errors
        self.scratch_dir = scratch_dir
        self.gzipped_output = gzipped_output
        self.checkpoint = checkpoint

    @staticmethod
    def _load_checkpoint(cwd):
        restart = -1
        run_log = []
        for chkpt in glob(pjoin(cwd, "custodian.chk.*.tar.gz")):
            jobno = int(chkpt.split(".")[-3])
            if jobno > restart:
                restart = jobno
                logger.info("Loading from checkpoint file {}...".format(
                    chkpt))
                t = tarfile.open(chkpt)
                t.extractall()
                #Log the corrections to a json file.
                with open(Custodian.LOG_FILE, "r") as f:
                    run_log = json.load(f)
        return restart, run_log

    @staticmethod
    def _delete_checkpoints(cwd):
        for f in glob(pjoin(cwd, "custodian.chk.*.tar.gz")):
            os.remove(f)

    @staticmethod
    def _save_checkpoint(cwd, index):
        try:
            Custodian._delete_checkpoints(cwd)
            name = shutil.make_archive(
                pjoin(cwd, "custodian.chk.{}".format(index)), "gztar")
            logger.info("Checkpoint written to {}".format(name))
        except Exception as ex:
            logger.info("Checkpointing failed")

    def run(self):
        """
        Runs the job.

        Returns:
            All errors encountered as a list of list.
            [[error_dicts for job 1], [error_dicts for job 2], ....]
        """
        cwd = os.getcwd()

        with ScratchDir(self.scratch_dir, create_symbolic_link=True,
                        copy_to_current_on_exit=True,
                        copy_from_current_on_enter=True) as temp_dir:
            total_errors = 0
            unrecoverable = False
            start = datetime.datetime.now()
            logger.info("Run started at {} in {}.".format(
                start, temp_dir))

            if self.checkpoint:
                restart, run_log = Custodian._load_checkpoint(cwd)
            else:
                restart, run_log = -1, []

            for i, job in enumerate(self.jobs):
                if i <= restart:
                    #Skip all jobs until the restart point.
                    continue
                run_log.append({"job": job.to_dict, "corrections": []})
                for attempt in xrange(self.max_errors):
                    logger.info(
                        "Starting job no. {} ({}) attempt no. {}. Errors "
                        "thus far = {}.".format(
                            i + 1, job.name, attempt + 1, total_errors))

                    # If this is the start of the job, do the setup.
                    if not run_log[-1]["corrections"]:
                        job.setup()

                    p = job.run()
                    # Check for errors using the error handlers and perform
                    # corrections.
                    has_error = False

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
                                    corrections = _do_check(
                                        self.monitors,
                                        terminate_func=p.terminate,
                                        skip_over_errors=self.skip_over_errors)
                                    if len(corrections) > 0:
                                        has_error = True
                                        total_errors += len(corrections)
                                        run_log[-1]["corrections"].extend(
                                            corrections)
                        else:
                            p.wait()

                    # Check for errors again, since in some cases non-monitor
                    # handlers fix the problems detected by monitors
                    # if an error has been found, not all handlers need to run
                    if has_error:
                        remaining_handlers = filter(lambda x: not x.is_monitor,
                                                    self.handlers)
                    else:
                        remaining_handlers = self.handlers

                    corrections = _do_check(
                        remaining_handlers,
                        skip_over_errors=self.skip_over_errors)
                    if len(corrections) > 0:
                        has_error = True
                        total_errors += len(corrections)
                        run_log[-1]["corrections"].extend(corrections)

                    #Log the corrections to a json file.
                    with open(Custodian.LOG_FILE, "w") as f:
                        logger.info("Logging to {}...".format(
                            Custodian.LOG_FILE))
                        json.dump(run_log, f, indent=4)

                    # If there are no errors detected, perform
                    # postprocessing and exit.
                    if not has_error:
                        job.postprocess()
                        break
                    elif run_log[-1]["corrections"][-1]["actions"] is None:
                        # Check if there has been an unrecoverable error.
                        logger.info("Unrecoverable error.")
                        unrecoverable = True
                        break
                    elif total_errors >= self.max_errors:
                        logger.info("Max errors reached.")
                        break

                if unrecoverable or total_errors >= self.max_errors:
                    break

                # Checkpoint after each job so that we can recover from last
                # point and remove old checkpoints
                if self.checkpoint:
                    Custodian._save_checkpoint(cwd, i)

            end = datetime.datetime.now()
            logger.info("Run ended at {}.".format(end))
            run_time = end - start

            logger.info("Run completed. Total time taken = {}."
                         .format(run_time))

            if self.gzipped_output:
                gzip_dir(".")

            if total_errors >= self.max_errors or unrecoverable:
                raise RuntimeError("{} errors reached. Unrecoverable? {}. "
                                   "Exited...".format(self.max_errors,
                                                      unrecoverable))
            elif not unrecoverable:
                #Cleanup checkpoint files (if any) if run is successful.
                Custodian._delete_checkpoints(cwd)

        return run_log


def _do_check(handlers, terminate_func=None, skip_over_errors=False):
    corrections = []
    for h in handlers:
        try:
            if h.check():
                if terminate_func is not None and h.is_terminating:
                    terminate_func()
                d = h.correct()
                logger.error(str(d))
                corrections.append(d)
        except Exception as ex:
            if not skip_over_errors:
                raise
            else:
                corrections.append(
                    {"errors": ["Bad handler " + str(h)],
                     "actions": []})
    return corrections


class JSONSerializable(object):
    """
    Base class to be inherited to provide useful standard json serialization
    and deserialization protocols based on init args.
    """

    @property
    def to_dict(self):
        d = {"@module": self.__class__.__module__,
             "@class": self.__class__.__name__}
        if hasattr(self, "__init__"):
            for c in inspect.getargspec(self.__init__).args:
                if c != "self":
                    a = self.__getattribute__(c)
                    if hasattr(a, "to_dict"):
                        a = a.to_dict
                    d[c] = a
        return d

    @classmethod
    def from_dict(cls, d):
        """
        This method should return the ErrorHandler from a dict representation
        of the object given by the to_dict property.
        """
        kwargs = {k: v for k, v in d.items()
                  if k in inspect.getargspec(cls.__init__).args}
        return cls(**kwargs)


class ErrorHandler(JSONSerializable):
    """
    Abstract base class defining the interface for an ErrorHandler.
    """
    __metaclass__ = ABCMeta

    is_monitor = False
    """
    This class roperty indicates whether the error handler is a monitor,
    i.e., a handler that monitors a job as it is running. If a
    monitor-type handler notices an error, the job will be sent a
    termination signal, the error is then corrected,
    and then the job is restarted. This is useful for catching errors
    that occur early in the run but do not cause immediate failure.
    """

    is_terminating = True
    """
    Whether this handler terminates a job upon error detection. By
    default, this is True, which means that the current Job will be
    terminated upon error detection, corrections applied,
    and restarted. In some instances, some errors may not need the job to be
    terminated or may need to wait for some other event to terminate a job.
    For example, a particular error may require a flag to be set to request
    a job to terminate gracefully once it finishes its current task. The
    handler to set the flag should be classified as is_terminating = False to
    not terminate the job.
    """

    @abstractmethod
    def check(self):
        """
        This method is called at the end of a job.

        Returns:
            (bool) Indicating if errors are detected.
        """
        pass

    @abstractmethod
    def correct(self):
        """
        This method is called at the end of a job when an error is detected.
        It should perform any corrective measures relating to the detected
        error.

        Returns:
            (dict) JSON serializable dict that describes the errors and
            actions taken. E.g.
            {"errors": list_of_errors, "actions": list_of_actions_taken}.
            If this is an unfixable error, actions should be set to None.
        """
        pass


class Job(JSONSerializable):
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
        checking (monitoring) is desired, this must return a Popen process.
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

    @property
    def name(self):
        """
        A nice string name for the job.
        """
        return self.__class__.__name__
