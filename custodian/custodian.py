"""
This module implements the main Custodian class, which manages a list of jobs
given a set of error handlers, the abstract base classes for the
ErrorHandlers and Jobs.
"""

import datetime
import logging
import os
import subprocess
import sys
import tarfile
import time
import warnings
from abc import abstractmethod
from ast import literal_eval
from glob import glob
from itertools import islice

from monty.json import MontyDecoder, MontyEncoder, MSONable
from monty.serialization import dumpfn, loadfn
from monty.shutil import gzip_dir
from monty.tempfile import ScratchDir

from .utils import get_execution_host_info

__author__ = "Shyue Ping Ong, William Davidson Richards"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.2"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "Sep 17 2014"

logger = logging.getLogger(__name__)

# Sentry.io is a service to aggregate logs remotely, this is useful
# for Custodian to get statistics on which errors are most common.
# If you do not have a SENTRY_DSN environment variable set, or do
# not have CUSTODIAN_REPORTING_OPT_IN set to True, then
# Sentry will not be enabled.

SENTRY_DSN = None
if "SENTRY_DSN" in os.environ:
    SENTRY_DSN = os.environ["SENTRY_DSN"]
elif "CUSTODIAN_REPORTING_OPT_IN" in os.environ:
    # check for environment variable to automatically set SENTRY_DSN
    # will set for True, true, TRUE, etc.
    if literal_eval(os.environ.get("CUSTODIAN_REPORTING_OPT_IN", "False").title()):
        SENTRY_DSN = "https://0f7291738eb042a3af671df9fc68ae2a@sentry.io/1470881"

if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN)  # pylint: disable=E0110

    with sentry_sdk.configure_scope() as scope:
        from getpass import getuser

        try:
            scope.user = {"username": getuser()}
        except Exception:
            pass

        import socket

        scope.set_tag("hostname", socket.gethostname())


class Custodian:
    """
    The Custodian class is the manager for a list of jobs given a list of
    error handlers. The way it works is as follows:

    1. Let's say you have defined a list of jobs as [job1, job2, job3, ...] and
       you have defined a list of possible error handlers as [err1, err2, ...]
    2. Custodian will run the jobs in the order of job1, job2, ... During each
       job, custodian will monitor for errors using the handlers that have
       is_monitor == True. If an error is detected, corrective measures are
       taken and the particular job is rerun.
    3. At the end of each individual job, Custodian will run through the list of
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

    def __init__(
        self,
        handlers,
        jobs,
        validators=None,
        max_errors_per_job=None,
        max_errors=1,
        polling_time_step=10,
        monitor_freq=30,
        skip_over_errors=False,
        scratch_dir=None,
        gzipped_output=False,
        checkpoint=False,
        terminate_func=None,
        terminate_on_nonzero_returncode=True,
        **kwargs,
    ):
        """
        Initializes a Custodian from a list of jobs and error handlers.

        Args:
            handlers ([ErrorHandler]): Error handlers. In order of priority of
                fixing.
            jobs ([Job]): Sequence of Jobs to be run. Note that this can be
                any sequence or even a generator yielding jobs.
            validators([Validator]): Validators to ensure job success
            max_errors_per_job (int): Maximum number of errors per job allowed
                before exiting. Defaults to None, which means it is set to be
                equal to max_errors..
            max_errors (int): Maximum number of total errors allowed before
                exiting. Defaults to 1.
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
            terminate_on_nonzero_returncode (bool): If True, a non-zero return
                code on any Job will result in a termination. Defaults to True.
        """
        self.max_errors = max_errors
        self.max_errors_per_job = max_errors_per_job or max_errors
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
        self.errors_current_job = 0
        self.total_errors = 0
        self.terminate_func = terminate_func
        self.terminate_on_nonzero_returncode = terminate_on_nonzero_returncode
        self.finished = False

    @staticmethod
    def _load_checkpoint(cwd):
        restart = 0
        run_log = []
        chkpts = glob(os.path.join(cwd, "custodian.chk.*.tar.gz"))
        if chkpts:
            chkpt = sorted(chkpts, key=lambda c: int(c.split(".")[-3]))[0]
            restart = int(chkpt.split(".")[-3])
            logger.info(f"Loading from checkpoint file {chkpt}...")
            with tarfile.open(chkpt) as t:

                def is_within_directory(directory, target):
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)

                    prefix = os.path.commonprefix([abs_directory, abs_target])

                    return prefix == abs_directory

                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")

                    tar.extractall(path, members, numeric_owner=numeric_owner)

                safe_extract(t)
            # Log the corrections to a json file.
            run_log = loadfn(Custodian.LOG_FILE, cls=MontyDecoder)

        return restart, run_log

    @staticmethod
    def _delete_checkpoints(cwd):
        for f in glob(os.path.join(cwd, "custodian.chk.*.tar.gz")):
            os.remove(f)

    @staticmethod
    def _save_checkpoint(cwd, index):
        try:
            Custodian._delete_checkpoints(cwd)
            n = os.path.join(cwd, f"custodian.chk.{index}.tar.gz")
            with tarfile.open(n, mode="w:gz", compresslevel=3) as f:
                f.add(cwd, arcname=".")
            logger.info(f"Checkpoint written to {n}")
        except Exception:
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
                YAML format for the usual MP workflow is given as follows

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
                specified via "job": <explicit path>, and all parameters are
                specified via `params` which is a dict.

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

        return cls(jobs=jobs, handlers=handlers, validators=validators, **custodian_params)

    def run(self):
        """
        Runs all jobs.

        Returns:
            All errors encountered as a list of list.
            [[error_dicts for job 1], [error_dicts for job 2], ....]

        Raises:
            ValidationError: if a job fails validation
            ReturnCodeError: if the process has a return code different from 0
            NonRecoverableError: if an unrecoverable occurs
            MaxCorrectionsPerJobError: if max_errors_per_job is reached
            MaxCorrectionsError: if max_errors is reached
            MaxCorrectionsPerHandlerError: if max_errors_per_handler is reached
        """
        cwd = os.getcwd()

        with ScratchDir(
            self.scratch_dir,
            create_symbolic_link=True,
            copy_to_current_on_exit=True,
            copy_from_current_on_enter=True,
        ) as temp_dir:
            self.total_errors = 0
            start = datetime.datetime.now()
            logger.info(f"Run started at {start} in {temp_dir}.")
            v = sys.version.replace("\n", " ")
            logger.info(f"Custodian running on Python version {v}")
            host, cluster = get_execution_host_info()
            logger.info(f"Hostname: {host}, Cluster: {cluster}")

            try:
                # skip jobs until the restart
                for job_n, job in islice(enumerate(self.jobs, 1), self.restart, None):
                    self._run_job(job_n, job)
                    # We do a dump of the run log after each job.
                    dumpfn(self.run_log, Custodian.LOG_FILE, cls=MontyEncoder, indent=4)
                    # Checkpoint after each job so that we can recover from last
                    # point and remove old checkpoints
                    if self.checkpoint:
                        self.restart = job_n
                        Custodian._save_checkpoint(cwd, job_n)
            except CustodianError as ex:
                logger.error(ex.message)
                if ex.raises:
                    raise
            finally:
                # Log the corrections to a json file.
                logger.info(f"Logging to {Custodian.LOG_FILE}...")
                dumpfn(self.run_log, Custodian.LOG_FILE, cls=MontyEncoder, indent=4)
                end = datetime.datetime.now()
                logger.info(f"Run ended at {end}.")
                run_time = end - start
                logger.info(f"Run completed. Total time taken = {run_time}.")
                if self.gzipped_output:
                    gzip_dir(".")

            # Cleanup checkpoint files (if any) if run is successful.
            Custodian._delete_checkpoints(cwd)

        return self.run_log

    def _run_job(self, job_n, job):
        """
        Runs a single job.

        Args:
            job_n: job number (1 index)
            job: Custodian job


        Raises:
            ValidationError: if a job fails validation
            ReturnCodeError: if the process has a return code different from 0
            NonRecoverableError: if an unrecoverable occurs
            MaxCorrectionsPerJobError: if max_errors_per_job is reached
            MaxCorrectionsError: if max_errors is reached
            MaxCorrectionsPerHandlerError: if max_errors_per_handler is reached
        """
        self.run_log.append(
            {
                "job": job.as_dict(),
                "corrections": [],
                "handler": None,
                "validator": None,
                "max_errors": False,
                "max_errors_per_job": False,
                "max_errors_per_handler": False,
                "nonzero_return_code": False,
            }
        )
        self.errors_current_job = 0
        # reset the counters of the number of times a correction has been
        # applied for each handler
        for h in self.handlers:
            h.n_applied_corrections = 0

        job.setup()

        attempt = 0
        while self.total_errors < self.max_errors and self.errors_current_job < self.max_errors_per_job:
            attempt += 1
            logger.info(
                f"Starting job no. {job_n} ({job.name}) attempt no. {attempt}. Total errors and "
                f"errors in job thus far = {self.total_errors}, {self.errors_current_job}."
            )

            p = job.run()
            # Check for errors using the error handlers and perform
            # corrections.
            has_error = False
            zero_return_code = True

            # Choose the terminate function to run. If a terminate_func exists, this
            # should take priority, followed by Job.terminate if implemented, and finally
            # subprocess.Popen.terminate if neither of the former exist.
            terminate = self.terminate_func or job.terminate or p.terminate

            # While the job is running, we use the handlers that are
            # monitors to monitor the job.
            if isinstance(p, subprocess.Popen):
                if self.monitors:
                    n = 0
                    while True:
                        n += 1
                        time.sleep(self.polling_time_step)
                        # We poll the process p to check if it is still running.
                        # Note that the process here is not the actual calculation
                        # but whatever is used to control the execution of the
                        # calculation executable. For instance; mpirun, srun, and so on.
                        if p.poll() is not None:
                            break
                        if n % self.monitor_freq == 0:
                            # At every self.polling_time_step * self.monitor_freq seconds,
                            # we check the job for errors using handlers that are monitors.
                            # In order to properly kill a running calculation, we use
                            # the appropriate implementation of terminate.
                            has_error = self._do_check(self.monitors, terminate)
                else:
                    p.wait()
                    if self.terminate_func is not None and self.terminate_func != p.terminate:
                        self.terminate_func()
                        time.sleep(self.polling_time_step)

                zero_return_code = p.returncode == 0

            logger.info(f"{job.name}.run has completed. " "Checking remaining handlers")
            # Check for errors again, since in some cases non-monitor
            # handlers fix the problems detected by monitors
            # if an error has been found, not all handlers need to run
            if has_error:
                self._do_check([h for h in self.handlers if not h.is_monitor])
            else:
                has_error = self._do_check(self.handlers)

            # If there are no errors detected, perform
            # postprocessing and exit.
            if not has_error:
                for v in self.validators:
                    if v.check():
                        self.run_log[-1]["validator"] = v
                        s = f"Validation failed: {v.__class__.__name__}"
                        raise ValidationError(s, True, v)
                if not zero_return_code:
                    if self.terminate_on_nonzero_returncode:
                        self.run_log[-1]["nonzero_return_code"] = True
                        s = f"Job return code is {p.returncode}. Terminating..."
                        logger.info(s)
                        raise ReturnCodeError(s, True)
                    warnings.warn("subprocess returned a non-zero return " "code. Check outputs carefully...")
                job.postprocess()
                return

            # Check that all errors could be handled
            for x in self.run_log[-1]["corrections"]:
                if not x["actions"] and x["handler"].raises_runtime_error:
                    self.run_log[-1]["handler"] = x["handler"]
                    s = f"Unrecoverable error for handler: {x['handler']}"
                    raise NonRecoverableError(s, True, x["handler"])
            for x in self.run_log[-1]["corrections"]:
                if not x["actions"]:
                    self.run_log[-1]["handler"] = x["handler"]
                    s = f"Unrecoverable error for handler: {x['handler']}"
                    raise NonRecoverableError(s, False, x["handler"])

        if self.errors_current_job >= self.max_errors_per_job:
            self.run_log[-1]["max_errors_per_job"] = True
            msg = f"Max errors per job reached: {self.max_errors_per_job}."
            logger.info(msg)
            raise MaxCorrectionsPerJobError(msg, True, self.max_errors_per_job, job)

        self.run_log[-1]["max_errors"] = True
        msg = f"Max errors reached: {self.max_errors}."
        logger.info(msg)
        raise MaxCorrectionsError(msg, True, self.max_errors)

    def run_interrupted(self):
        """
        Runs custodian in a interuppted mode, which sets up and
        validates jobs but doesn't run the executable

        Returns:
            number of remaining jobs

        Raises:
            ValidationError: if a job fails validation
            ReturnCodeError: if the process has a return code different from 0
            NonRecoverableError: if an unrecoverable occurs
            MaxCorrectionsPerJobError: if max_errors_per_job is reached
            MaxCorrectionsError: if max_errors is reached
            MaxCorrectionsPerHandlerError: if max_errors_per_handler is reached
        """
        start = datetime.datetime.now()
        try:
            cwd = os.getcwd()
            v = sys.version.replace("\n", " ")
            logger.info(f"Custodian started in singleshot mode at {start} in {cwd}.")
            logger.info(f"Custodian running on Python version {v}")

            # load run log
            if os.path.exists(Custodian.LOG_FILE):
                self.run_log = loadfn(Custodian.LOG_FILE, cls=MontyDecoder)

            if len(self.run_log) == 0:
                # starting up an initial job - setup input and quit
                job_n = 0
                job = self.jobs[job_n]
                logger.info(f"Setting up job no. 1 ({job.name}) ")
                job.setup()
                self.run_log.append({"job": job.as_dict(), "corrections": [], "job_n": job_n})
                return len(self.jobs)

            # Continuing after running calculation
            job_n = self.run_log[-1]["job_n"]
            job = self.jobs[job_n]

            # If we had to fix errors from a previous run, insert clean log
            # dict
            if len(self.run_log[-1]["corrections"]) > 0:
                logger.info(f"Reran {job.name}.run due to fixable errors")

            # check error handlers
            logger.info(f"Checking error handlers for {job.name}.run")
            if self._do_check(self.handlers):
                logger.info("Failed validation based on error handlers")
                # raise an error for an unrecoverable error
                for x in self.run_log[-1]["corrections"]:
                    if not x["actions"] and x["handler"].raises_runtime_error:
                        self.run_log[-1]["handler"] = x["handler"]
                        s = f"Unrecoverable error for handler: {x['handler']}. Raising RuntimeError"
                        raise NonRecoverableError(s, True, x["handler"])
                logger.info("Corrected input based on error handlers")
                # Return with more jobs to run if recoverable error caught
                # and corrected for
                return len(self.jobs) - job_n

            # check validators
            logger.info(f"Checking validator for {job.name}.run")
            for v in self.validators:
                if v.check():
                    self.run_log[-1]["validator"] = v
                    logger.info("Failed validation based on validator")
                    s = f"Validation failed: {v}"
                    raise ValidationError(s, True, v)

            logger.info(f"Postprocessing for {job.name}.run")
            job.postprocess()

            # IF DONE WITH ALL JOBS - DELETE ALL CHECKPOINTS AND RETURN
            # VALIDATED
            if len(self.jobs) == (job_n + 1):
                self.finished = True
                return 0

            # Setup next job_n
            job_n += 1
            job = self.jobs[job_n]
            self.run_log.append({"job": job.as_dict(), "corrections": [], "job_n": job_n})
            job.setup()
            return len(self.jobs) - job_n

        except CustodianError as ex:
            logger.error(ex.message)
            if ex.raises:
                raise

        finally:
            # Log the corrections to a json file.
            logger.info(f"Logging to {Custodian.LOG_FILE}...")
            dumpfn(self.run_log, Custodian.LOG_FILE, cls=MontyEncoder, indent=4)
            end = datetime.datetime.now()
            logger.info(f"Run ended at {end}.")
            run_time = end - start
            logger.info(f"Run completed. Total time taken = {run_time}.")
            if self.finished and self.gzipped_output:
                gzip_dir(".")
        return None

    def _do_check(self, handlers, terminate_func=None):
        """
        checks the specified handlers. Returns True iff errors caught
        """
        corrections = []
        for h in handlers:
            try:
                if h.check():
                    if h.max_num_corrections is not None and h.n_applied_corrections >= h.max_num_corrections:
                        msg = f"Maximum number of corrections {h.max_num_corrections} reached for handler {h}"
                        if h.raise_on_max:
                            self.run_log[-1]["handler"] = h
                            self.run_log[-1]["max_errors_per_handler"] = True
                            raise MaxCorrectionsPerHandlerError(msg, True, h.max_num_corrections, h)
                        logger.warning(msg + " Correction not applied.")
                        continue
                    if terminate_func is not None and h.is_terminating:
                        logger.info("Terminating job")
                        terminate_func()
                        # make sure we don't terminate twice
                        terminate_func = None
                    d = h.correct()
                    logger.error(h.__class__.__name__, extra=d)
                    d["handler"] = h
                    corrections.append(d)
                    h.n_applied_corrections += 1
            except Exception:
                if not self.skip_over_errors:
                    raise
                import traceback

                logger.error(f"Bad handler {h}")
                logger.error(traceback.format_exc())
                corrections.append({"errors": [f"Bad handler {h}"], "actions": []})
        self.total_errors += len(corrections)
        self.errors_current_job += len(corrections)
        self.run_log[-1]["corrections"].extend(corrections)
        # We do a dump of the run log after each check.
        dumpfn(self.run_log, Custodian.LOG_FILE, cls=MontyEncoder, indent=4)
        return len(corrections) > 0


class Job(MSONable):
    """
    Abstract base class defining the interface for a Job.
    """

    @abstractmethod
    def setup(self):
        """
        This method is run before the start of a job. Allows for some
        pre-processing.
        """

    @abstractmethod
    def run(self):
        """
        This method perform the actual work for the job. If parallel error
        checking (monitoring) is desired, this must return a Popen process.
        """

    @abstractmethod
    def postprocess(self):
        """
        This method is called at the end of a job, *after* error detection.
        This allows post-processing, such as cleanup, analysis of results,
        etc.
        """

    def terminate(self):
        """
        Implement termination function.
        """
        return None

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

    max_num_corrections = None
    raise_on_max = False
    """
    Whether corrections from this specific handler should be applied only a
    fixed maximum number of times on a single job (i.e. the counter is reset
    at the beginning of each job). If the maximum number is reached the code
    will either raise a MaxCorrectionsPerHandlerError (raise_on_max==True) or stops
    considering the correction (raise_on_max==False). If max_num_corrections
    is None this option is not considered. These options can be overridden
    as class attributes of the subclass or as customizable options setting
    an instance attribute from __init__.
    """

    @abstractmethod
    def check(self):
        """
        This method is called during the job (for monitors) or at the end of
        the job to check for errors.

        Returns:
            (bool) Indicating if errors are detected.
        """

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

    @property
    def n_applied_corrections(self):
        """
        The number of times the handler has given a correction and this
        has been applied.

        Returns:
            (int): the number of corrections applied.
        """
        try:
            return self._num_applied_corrections
        except AttributeError:
            self._num_applied_corrections = 0
            return self._num_applied_corrections

    @n_applied_corrections.setter
    def n_applied_corrections(self, value):
        """
        Setter for the number of corrections applied.

        Args:
             value(int): the number of corrections applied
        """
        self._num_applied_corrections = value


class Validator(MSONable):
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


class CustodianError(RuntimeError):
    """
    Exception class for Custodian errors.
    """

    def __init__(self, message, raises=False):
        """
        Initializes the error with a message.

        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should be raised outside custodian
        """
        super().__init__(message)
        self.raises = raises
        self.message = message


class ValidationError(CustodianError):
    """
    Error raised when a validator does not pass the check
    """

    def __init__(self, message, raises, validator):
        """
        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should be raised outside custodian
            validator (Validator): Validator that caused the exception.
        """
        super().__init__(message, raises)
        self.validator = validator


class NonRecoverableError(CustodianError):
    """
    Error raised when a handler found an error but could not fix it
    """

    def __init__(self, message, raises, handler):
        """
        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should be raised outside custodian
            handler (Handler): Handler that caused the exception.
        """
        super().__init__(message, raises)
        self.handler = handler


class ReturnCodeError(CustodianError):
    """
    Error raised when the process gave non zero return code
    """


class MaxCorrectionsError(CustodianError):
    """
    Error raised when the maximum allowed number of errors is reached
    """

    def __init__(self, message, raises, max_errors):
        """
        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should be raised outside custodian
            max_errors (int): the number of errors reached
        """
        super().__init__(message, raises)
        self.max_errors = max_errors


class MaxCorrectionsPerJobError(CustodianError):
    """
    Error raised when the maximum allowed number of errors per job is reached
    """

    def __init__(self, message, raises, max_errors_per_job, job):
        """
        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should be raised outside custodian
            max_errors_per_job (int): the number of errors per job reached
            job (Job): the job that was stopped
        """
        super().__init__(message, raises)
        self.max_errors_per_job = max_errors_per_job
        self.job = job


class MaxCorrectionsPerHandlerError(CustodianError):
    """
    Error raised when the maximum allowed number of errors per handler is reached
    """

    def __init__(self, message, raises, max_errors_per_handler, handler):
        """
        Args:
            message (str): Message passed to Exception
            raises (bool): Whether this should be raised outside custodian
            max_errors_per_handler (int): the number of errors per job reached
            handler (Handler): the handler that caused the exception
        """
        super().__init__(message, raises)
        self.max_errors_per_handler = max_errors_per_handler
        self.handler = handler
