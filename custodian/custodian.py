# coding: utf-8

from __future__ import unicode_literals, division

import logging
import subprocess
import sys
import datetime
import time
from glob import glob
import tarfile
import os
from abc import ABCMeta, abstractmethod
from itertools import islice

import six

from .utils import get_execution_host_info

from monty.tempfile import ScratchDir
from monty.shutil import gzip_dir
from monty.json import MSONable, MontyEncoder, MontyDecoder
from monty.serialization import loadfn, dumpfn

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
                 gzipped_output=False, checkpoint=False, terminate_func=None):
        """
        Initializes a Custodian from a list of jobs and error handler.s

        Args:
            handlers ([ErrorHandler]): Error handlers. In order of priority of
                fixing.
            jobs ([Job]): Sequence of Jobs to be run. Note that this can be
                any sequence or even a generator yielding jobs.
            validators([Validator]): Validators to ensure job success
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
            terminate_func (callable): A function to be called to terminate a
                running job. If None, the default is to call Popen.terminate.
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
        self.terminate_func = terminate_func
        self.finished = False

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
            # Log the corrections to a json file.
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
            n = pjoin(cwd, "custodian.chk.{}.tar.gz".format(index))
            with tarfile.open(n,  mode="w:gz", compresslevel=3) as f:
                f.add(cwd, arcname='.')
            logger.info("Checkpoint written to {}".format(n))
        except Exception as ex:
            logger.info("Checkpointing failed")
            import traceback
            logger.error(traceback.format_exc())

    @classmethod
    def from_spec(cls, spec):
        """
        Load a Custodian instance where the jobs are specified from a
        structure and a spec dict. This allows simple
        custom job sequences to be constructed quickly via a YAML file.

        Args:
            spec (dict): A dict specifying job. A sample of the dict in
                YAML format for the usual MP workflow is given as follows:

                ```
                jobs:
                - jb: custodian.vasp.jobs.VaspJob
                  params:
                    final: False
                    suffix: .relax1
                - jb: custodian.vasp.jobs.VaspJob
                  params:
                    final: True
                    suffix: .relax2
                    settings_override: {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}
                jobs_common_params:
                  vasp_cmd: /opt/vasp
                handlers:
                - hdlr: custodian.vasp.handlers.VaspErrorHandler
                - hdlr: custodian.vasp.handlers.AliasingErrorHandler
                - hdlr: custodian.vasp.handlers.MeshSymmetryHandler
                validators:
                - vldr: custodian.vasp.validators.VasprunXMLValidator
                custodian_params:
                  scratch_dir: /tmp
                ```

                The `jobs` key is a list of jobs. Each job is
                specified via "job": <explicit path>, and all parameters other
                than
                structure are specified via `params` which is a dict. `parents` is
                a special parameter, which provides the *indices* of the parents
                of that particular firework in the list.

                `common_params` specify a common set of parameters that are
                passed to all jobs, e.g., vasp_cmd.

        Returns:
            Custodian instance.
        """

        dec = MontyDecoder()

        def load_class(dotpath):
            modname, classname = dotpath.rsplit(".", 1)
            mod = __import__(modname, globals(), locals(), [classname], 0)
            return getattr(mod, classname)

        def process_params(d):
            decoded = {}
            for k, v in d.items():
                if k.startswith("$"):
                    if isinstance(v, list):
                        v = [os.path.expandvars(i) for i in v]
                    elif isinstance(v, dict):
                        v = {k2: os.path.expandvars(v2) for k2, v2 in v.items()}
                    else:
                        v = os.path.expandvars(v)
                decoded[k.strip("$")] = dec.process_decoded(v)
            return decoded

        jobs = []
        common_params = process_params(spec.get("jobs_common_params", {}))

        for d in spec["jobs"]:
            cls_ = load_class(d["jb"])
            params = process_params(d.get("params", {}))
            params.update(common_params)
            jobs.append(cls_(**params))

        handlers = []
        for d in spec.get("handlers", []):
            cls_ = load_class(d["hdlr"])
            params = process_params(d.get("params", {}))
            handlers.append(cls_(**params))

        validators = []
        for d in spec.get("validators", []):
            cls_ = load_class(d["vldr"])
            params = process_params(d.get("params", {}))
            validators.append(cls_(**params))

        custodian_params = process_params(spec.get("custodian_params", {}))

        return cls(jobs=jobs, handlers=handlers, validators=validators,
                   **custodian_params)

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
            logger.info("Hostname: {}, Cluster: {}".format(*get_execution_host_info()))

            try:
                # skip jobs until the restart
                for job_n, job in islice(enumerate(self.jobs, 1),
                                         self.restart, None):
                    self._run_job(job_n, job)
                    # Checkpoint after each job so that we can recover from last
                    # point and remove old checkpoints
                    if self.checkpoint:
                        self.restart = job_n
                        Custodian._save_checkpoint(cwd, job_n)
            except CustodianError as ex:
                logger.error(ex.message)
                if ex.raises:
                    raise RuntimeError("{} errors reached: {}. Exited..."
                                       .format(self.total_errors, ex))
            finally:
                # Log the corrections to a json file.
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

            # Cleanup checkpoint files (if any) if run is successful.
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
                        terminate = self.terminate_func or p.terminate
                        if n % self.monitor_freq == 0:
                            has_error = self._do_check(self.monitors,
                                                       terminate)
                        if terminate is not None and terminate != p.terminate:
                            time.sleep(self.polling_time_step)
                else:
                    p.wait()
                    if self.terminate_func is not None and self.terminate_func != p.terminate:
                        self.terminate_func()
                        time.sleep(self.polling_time_step)

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

            # Check that all errors could be handled
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

    def run_interrupted(self):
        """
        Runs custodian in a interuppted mode, which sets up and
        validates jobs but doesn't run the executable

        Returns:
            number of remaining jobs

        Raises:
            CustodianError on unrecoverable errors, and jobs that fail
            validation
        """

        try:
            cwd = os.getcwd()
            start = datetime.datetime.now()
            v = sys.version.replace("\n", " ")
            logger.info("Custodian started in singleshot mode at {} in {}."
                        .format(start, cwd))
            logger.info("Custodian running on Python version {}".format(v))

            # load run log
            if os.path.exists(Custodian.LOG_FILE):
                self.run_log = loadfn(Custodian.LOG_FILE, cls=MontyDecoder)

            if len(self.run_log) == 0:
                # starting up an initial job - setup input and quit
                job_n = 0
                job = self.jobs[job_n]
                logger.info("Setting up job no. 1 ({}) ".format(job.name))
                job.setup()
                self.run_log.append({"job": job.as_dict(), "corrections": [], 'job_n': job_n})
                return len(self.jobs)
            else:
                # Continuing after running calculation
                job_n = self.run_log[-1]['job_n']
                job = self.jobs[job_n]

                # If we had to fix errors from a previous run, insert clean log
                # dict
                if len(self.run_log[-1]['corrections']) > 0:
                    logger.info("Reran {}.run due to fixable errors".format(job.name))

                # check error handlers
                logger.info("Checking error handlers for {}.run".format(job.name))
                if self._do_check(self.handlers):
                    logger.info("Failed validation based on error handlers")
                    # raise an error for an unrecoverable error
                    for x in self.run_log[-1]["corrections"]:
                        if not x["actions"] and x["handler"].raises_runtime_error:
                            s = "Unrecoverable error for handler: {}. " \
                                "Raising RuntimeError".format(x["handler"])
                            raise CustodianError(s, True, x["handler"])
                    logger.info("Corrected input based on error handlers")
                    # Return with more jobs to run if recoverable error caught
                    # and corrected for
                    return len(self.jobs) - job_n

                # check validators
                logger.info("Checking validator for {}.run".format(job.name))
                for v in self.validators:
                    if v.check():
                        logger.info("Failed validation based on validator")
                        s = "Validation failed: {}".format(v)
                        raise CustodianError(s, True, v)

                logger.info("Postprocessing for {}.run".format(job.name))
                job.postprocess()

                # IF DONE WITH ALL JOBS - DELETE ALL CHECKPOINTS AND RETURN
                # VALIDATED
                if len(self.jobs) == (job_n + 1):
                    self.finished = True
                    return 0

                # Setup next job_n
                job_n += 1
                job = self.jobs[job_n]
                self.run_log.append({"job": job.as_dict(), "corrections": [],
                                     'job_n': job_n})
                job.setup()
                return len(self.jobs) - job_n

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
            if self.finished and self.gzipped_output:
                gzip_dir(".")

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
                        # make sure we don't terminate twice
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


class Job(six.with_metaclass(ABCMeta, MSONable)):
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


class ErrorHandler(MSONable):
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


class Validator(six.with_metaclass(ABCMeta, MSONable)):
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
        super(CustodianError, self).__init__(self, message)
        self.raises = raises
        self.validator = validator
        self.message = message
