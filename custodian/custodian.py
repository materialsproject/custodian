# coding: utf-8

from __future__ import unicode_literals, division

"""
This module implements the main Custodian class, which manages a list of jobs
given a set of error handlers, the abstract base classes for the
ErrorHandlers and Jobs.
"""

__author__ = "Shyue Ping Ong, William Davidson Richards"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.2"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "Sep 17 2014"

import logging
import inspect
import subprocess
import sys
import datetime
import time
from glob import glob
import tarfile
import os
import shutil
from abc import ABCMeta, abstractmethod
from itertools import islice

import six

from monty.tempfile import ScratchDir
from monty.shutil import gzip_dir
from monty.json import MSONable, MontyEncoder, MontyDecoder
from monty.serialization import loadfn, dumpfn


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

    def __init__(self, handlers, jobs, validators=None, max_errors=1,
                 polling_time_step=10, monitor_freq=30,
                 skip_over_errors=False, scratch_dir=None,
                 gzipped_output=False, checkpoint=False):
        """
        Initializes a Custodian from a list of jobs and error handler.s

        Args:
            handlers ([ErrorHandler]): Error handlers. In order of priority of
                fixing.
            jobs ([Job]): Sequence of Jobs to be run. Note that this can be
                any sequence or even a generator yielding jobs.
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
        self.validators = validators or []
        self.monitors = [h for h in handlers if h.is_monitor]
        self.polling_time_step = polling_time_step
        self.monitor_freq = monitor_freq
        self.skip_over_errors = skip_over_errors
        self.scratch_dir = scratch_dir
        self.gzipped_output = gzipped_output
        self.checkpoint = checkpoint
        cwd = os.getcwd()
        if self.checkpoint:
            self.restart, self.run_log = Custodian._load_checkpoint(cwd)
        else:
            self.restart = 0
            self.run_log = []
        self.total_errors = 0

    @staticmethod
    def _load_checkpoint(cwd):
        restart = 0
        run_log = []
        chkpts = glob(pjoin(cwd, "custodian.chk.*.tar.gz"))
        if chkpts:
            chkpt = sorted(chkpts, key=lambda c: int(c.split(".")[-3]))[0]
            restart = int(chkpt.split(".")[-3])
            logger.info("Loading from checkpoint file {}...".format(chkpt))
            t = tarfile.open(chkpt)
            t.extractall()
            #Log the corrections to a json file.
            run_log = loadfn(Custodian.LOG_FILE, cls=MontyDecoder)

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
            import traceback
            logger.error(traceback.format_exc())

    def run(self):
        """
        Runs all the jobs jobs.

        Returns:
            All errors encountered as a list of list.
            [[error_dicts for job 1], [error_dicts for job 2], ....]
        """
        cwd = os.getcwd()

        with ScratchDir(self.scratch_dir, create_symbolic_link=True,
                        copy_to_current_on_exit=True,
                        copy_from_current_on_enter=True) as temp_dir:
            self.total_errors = 0
            start = datetime.datetime.now()
            logger.info("Run started at {} in {}.".format(
                start, temp_dir))
            v = sys.version.replace("\n", " ")
            logger.info("Custodian running on Python version {}".format(v))

            try:
                #skip jobs until the restart
                for job_n, job in islice(enumerate(self.jobs, 1),
                                         self.restart, None):
                    self._run_job(job_n, job)
                    # Checkpoint after each job so that we can recover from last
                    # point and remove old checkpoints
                    if self.checkpoint and job_n != len(self.jobs):
                        Custodian._save_checkpoint(cwd, job_n)
            except CustodianError as ex:
                logger.error(ex.message)
                if ex.raises:
                    raise RuntimeError("{} errors reached: {}. Exited..."
                                       .format(self.total_errors, ex))
            finally:
                #Log the corrections to a json file.
                logger.info("Logging to {}...".format(Custodian.LOG_FILE))
                dumpfn(self.run_log, Custodian.LOG_FILE, cls=MontyEncoder,
                       indent=4)
                end = datetime.datetime.now()
                logger.info("Run ended at {}.".format(end))
                run_time = end - start
                logger.info("Run completed. Total time taken = {}."
                            .format(run_time))
                if self.gzipped_output:
                    gzip_dir(".")

            #Cleanup checkpoint files (if any) if run is successful.
            Custodian._delete_checkpoints(cwd)

        return self.run_log

    def _run_job(self, job_n, job):
        """
        Args:
            job_n: job number (1 index)
            job: Custodian job
        Runs a single job,

        Raises:
            CustodianError on unrecoverable errors, max errors, and jobs
            that fail validation
        """
        self.run_log.append({"job": job.as_dict(), "corrections": []})
        job.setup()

        for attempt in range(1, self.max_errors - self.total_errors + 1):
            logger.info(
                "Starting job no. {} ({}) attempt no. {}. Errors "
                "thus far = {}.".format(
                    job_n, job.name, attempt, self.total_errors))

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
                            has_error = self._do_check(self.monitors,
                                                       p.terminate)
                else:
                    p.wait()

            logger.info("{}.run has completed. "
                        "Checking remaining handlers".format(job.name))
            # Check for errors again, since in some cases non-monitor
            # handlers fix the problems detected by monitors
            # if an error has been found, not all handlers need to run
            if has_error:
                self._do_check([h for h in self.handlers
                                if not h.is_monitor])
            else:
                has_error = self._do_check(self.handlers)

            # If there are no errors detected, perform
            # postprocessing and exit.
            if not has_error:
                for v in self.validators:
                    if v.check():
                        s = "Validation failed: {}".format(v)
                        raise CustodianError(s, True, v)
                job.postprocess()
                return

            #check that all errors could be handled
            for x in self.run_log[-1]["corrections"]:
                if not x["actions"] and x["handler"].raises_runtime_error:
                    s = "Unrecoverable error for handler: {}. " \
                        "Raising RuntimeError".format(x["handler"])
                    raise CustodianError(s, True, x["handler"])
            for x in self.run_log[-1]["corrections"]:
                if not x["actions"]:
                    s = "Unrecoverable error for handler: %s" % x["handler"]
                    raise CustodianError(s, False, x["handler"])

        logger.info("Max errors reached.")
        raise CustodianError("MaxErrors", True)

    def _do_check(self, handlers, terminate_func=None):
        """
        checks the specified handlers. Returns True iff errors caught
        """
        corrections = []
        for h in handlers:
            try:
                if h.check():
                    if terminate_func is not None and h.is_terminating:
                        logger.info("Terminating job")
                        terminate_func()
                        #make sure we don't terminate twice
                        terminate_func = None
                    d = h.correct()
                    d["handler"] = h
                    logger.error(str(d))
                    corrections.append(d)
            except Exception:
                if not self.skip_over_errors:
                    raise
                else:
                    import traceback
                    logger.error("Bad handler %s " % h)
                    logger.error(traceback.format_exc())
                    corrections.append(
                        {"errors": ["Bad handler %s " % h],
                         "actions": []})
        self.total_errors += len(corrections)
        self.run_log[-1]["corrections"].extend(corrections)
        return len(corrections) > 0


class JSONSerializable(MSONable):
    """
    Base class to be inherited to provide useful standard json serialization
    and deserialization protocols based on init args.
    """

    def as_dict(self):
        d = {"@module": self.__class__.__module__,
             "@class": self.__class__.__name__}
        if hasattr(self, "__init__"):
            for c in inspect.getargspec(self.__init__).args:
                if c != "self":
                    a = self.__getattribute__(c)
                    if hasattr(a, "as_dict"):
                        a = a.as_dict()
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

    @classmethod
    def __str__(cls):
        return cls.__name__

    @classmethod
    def __repr__(cls):
        return cls.__name__


class Job(six.with_metaclass(ABCMeta, JSONSerializable)):
    """
    Abstract base class defining the interface for a Job.
    """

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


class ErrorHandler(JSONSerializable):
    """
    Abstract base class defining the interface for an ErrorHandler.
    """

    is_monitor = False
    """
    This class property indicates whether the error handler is a monitor,
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

    raises_runtime_error = True
    """
    Whether this handler causes custodian to raise a runtime error if it cannot
    handle the error (i.e. if correct returns a dict with "actions":None, or
    "actions":[])
    """

    @abstractmethod
    def check(self):
        """
        This method is called during the job (for monitors) or at the end of
        the job to check for errors.

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


class Validator(six.with_metaclass(ABCMeta, JSONSerializable)):
    """
    Abstract base class defining the interface for a Validator. A Validator
    differs from an ErrorHandler in that it does not correct a run and is run
    only at the end of a Job. If errors are detected by a Validator, a run is
    immediately terminated.
    """

    @abstractmethod
    def check(self):
        """
        This method is called at the end of a job.

        Returns:
            (bool) Indicating if errors are detected.
        """
        pass


class CustodianError(Exception):
    """
    Exception class for Custodian errors.
    """

    def __init__(self, message, raises=False, validator=None):
        """
        Initializes the error with a message.

        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should raise a runtime error when caught
            validator (Validator/ErrorHandler): Validator or ErrorHandler that
                caused the exception.
        """
        Exception.__init__(self, message)
        self.raises = raises
        self.validator = validator
        self.message = message
