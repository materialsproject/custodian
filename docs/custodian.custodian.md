---
layout: default
title: custodian.custodian.md
nav_exclude: true
---

# custodian.custodian module

This module implements the main Custodian class, which manages a list of jobs
given a set of error handlers, the abstract base classes for the
ErrorHandlers and Jobs.

## *class* custodian.custodian.Custodian(handlers, jobs, validators=None, max_errors_per_job=None, max_errors=1, polling_time_step=10, monitor_freq=30, skip_over_errors=False, scratch_dir=None, gzipped_output=False, checkpoint=False, terminate_func=None, terminate_on_nonzero_returncode=True)

Bases: `object`

The Custodian class is the manager for a list of jobs given a list of
error handlers. The way it works is as follows:

1. Let’s say you have defined a list of jobs as [job1, job2, job3, …] and
   you have defined a list of possible error handlers as [err1, err2, …]
2. Custodian will run the jobs in the order of job1, job2, … During each
   job, custodian will monitor for errors using the handlers that have
   is_monitor == True. If an error is detected, corrective measures are
   taken and the particular job is rerun.
3. At the end of each individual job, Custodian will run through the list of
   error handlers that have is_monitor == False. If an error is detected,
   corrective measures are taken and the particular job is rerun.

<!-- attribute: max_errors

Maximum number of errors allowed. -->
<!-- attribute: handlers

All error handlers (including monitors). All error handlers are used
to check for errors at the end of a run. -->
<!-- attribute: monitors

Error handlers that are Monitors, i.e., handlers that monitors a job
as it is being run. -->
<!-- attribute: polling_time_step

The length of time in seconds between steps in which a job is
checked for completion. -->
<!-- attribute: monitor_freq

The number of polling steps before monitoring occurs. For example,
if you have a polling_time_step of 10 seconds and a monitor_freq of
30, this means that Custodian uses the monitors to check for errors
every 30 x 10 = 300 seconds, i.e., 5 minutes. -->

Initializes a Custodian from a list of jobs and error handlers.

* **Parameters**
  * **handlers** (  *[**ErrorHandler**]*) – Error handlers. In order of priority of
    fixing.
  * **jobs** (  *[**Job**]*) – Sequence of Jobs to be run. Note that this can be
    any sequence or even a generator yielding jobs.
  * **validators** (  *[**Validator**]*) – Validators to ensure job success
  * **max_errors_per_job** (*int*) – Maximum number of errors per job allowed
    before exiting. Defaults to None, which means it is set to be
    equal to max_errors..
  * **max_errors** (*int*) – Maximum number of total errors allowed before
    exiting. Defaults to 1.
  * **polling_time_step** (*int*) – The length of time in seconds between
    steps in which a job is checked for completion. Defaults to
    10 secs.
  * **monitor_freq** (*int*) – The number of polling steps before monitoring
    occurs. For example, if you have a polling_time_step of 10
    seconds and a monitor_freq of 30, this means that Custodian
    uses the monitors to check for errors every 30 x 10 = 300
    seconds, i.e., 5 minutes.
  * **skip_over_errors** (*bool*) – If set to True, custodian will skip over
    error handlers that failed (raised an Exception of some sort).
    Otherwise, custodian will simply exit on unrecoverable errors.
    The former will lead to potentially more robust performance,
    but may make it difficult to improve handlers. The latter
    will allow one to catch potentially bad error handler
    implementations. Defaults to False.
  * **scratch_dir** (*str*) – If this is set, any files in the current
    directory are copied to a temporary directory in a scratch
    space first before any jobs are performed, and moved back to
    the current directory upon completion of all jobs. This is
    useful in some setups where a scratch partition has much
    faster IO. To use this, set scratch_dir=root of directory you
    want to use for runs. There is no need to provide unique
    directory names; we will use python’s tempfile creation
    mechanisms. A symbolic link is created during the course of
    the run in the working directory called “scratch_link” as
    users may want to sometimes check the output during the
    course of a run. If this is None (the default), the run is
    performed in the current working directory.
  * **gzipped_output** (*bool*) – Whether to gzip the final output to save
    space. Defaults to False.
  * **checkpoint** (*bool*) – Whether to checkpoint after each successful Job.
    Checkpoints are stored as custodian.chk.#.tar.gz files. Defaults
    to False.
  * **terminate_func** (*callable*) – A function to be called to terminate a
    running job. If None, the default is to call Popen.terminate.
  * **terminate_on_nonzero_returncode** (*bool*) – If True, a non-zero return
    code on any Job will result in a termination. Defaults to True.

### LOG_FILE(_ = ‘custodian.json_ )

### *classmethod* from_spec(spec)

Load a Custodian instance where the jobs are specified from a
structure and a spec dict. This allows simple
custom job sequences to be constructed quickly via a YAML file.

* **Parameters**

  **spec** (*dict*) – A dict specifying job. A sample of the dict in
  YAML format for the usual MP workflow is given as follows
  ```default
  ``
  ```

  \`
  jobs:
  - jb: custodian.vasp.jobs.VaspJob

  > params:
  > ```none
  > final: False
  > suffix: .relax1
  > ```
  * jb: custodian.vasp.jobs.VaspJob
    params:

  > final: True
  > suffix: .relax2
  > settings_override: {“file”: “CONTCAR”, “action”: {“_file_copy”: {“dest”: “POSCAR”}}

  jobs_common_params:
  ```none
    vasp_cmd: /opt/vasp
  ```

  handlers:
  - hdlr: custodian.vasp.handlers.VaspErrorHandler
  - hdlr: custodian.vasp.handlers.AliasingErrorHandler
  - hdlr: custodian.vasp.handlers.MeshSymmetryHandler
    validators:
  - vldr: custodian.vasp.validators.VasprunXMLValidator
    custodian_params:

  > scratch_dir: /tmp
  ```default
  ``
  ```

  ```default
  `
  ```

  The jobs key is a list of jobs. Each job is
  specified via “job”: <explicit path>, and all parameters are
  specified via params which is a dict.

  common_params specify a common set of parameters that are
  passed to all jobs, e.g., vasp_cmd.
* **Returns**

  Custodian instance.

### run()

Runs all jobs.

* **Returns**

  All errors encountered as a list of list.
  [[error_dicts for job 1], [error_dicts for job 2], ….]
* **Raises**
  * **ValidationError** – if a job fails validation
  * **ReturnCodeError** – if the process has a return code different from 0
  * **NonRecoverableError** – if an unrecoverable occurs
  * **MaxCorrectionsPerJobError** – if max_errors_per_job is reached
  * **MaxCorrectionsError** – if max_errors is reached
  * **MaxCorrectionsPerHandlerError** – if max_errors_per_handler is reached

### run_interrupted()

Runs custodian in a interuppted mode, which sets up and
validates jobs but doesn’t run the executable

* **Returns**

  number of remaining jobs
* **Raises**
  * **ValidationError** – if a job fails validation
  * **ReturnCodeError** – if the process has a return code different from 0
  * **NonRecoverableError** – if an unrecoverable occurs
  * **MaxCorrectionsPerJobError** – if max_errors_per_job is reached
  * **MaxCorrectionsError** – if max_errors is reached
  * **MaxCorrectionsPerHandlerError** – if max_errors_per_handler is reached

## *exception* custodian.custodian.CustodianError(message, raises=False)

Bases: `RuntimeError`

Exception class for Custodian errors.

Initializes the error with a message.

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian

## *class* custodian.custodian.ErrorHandler()

Bases: `MSONable`

Abstract base class defining the interface for an ErrorHandler.

### *abstract* check()

This method is called during the job (for monitors) or at the end of
the job to check for errors.

* **Returns**

  (bool) Indicating if errors are detected.

### *abstract* correct()

This method is called at the end of a job when an error is detected.
It should perform any corrective measures relating to the detected
error.

* **Returns**

  (dict) JSON serializable dict that describes the errors and
  actions taken. E.g.
  {“errors”: list_of_errors, “actions”: list_of_actions_taken}.
  If this is an unfixable error, actions should be set to None.

### is_monitor(_ = Fals_ )

This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.

### is_terminating(_ = Tru_ )

Whether this handler terminates a job upon error detection. By
default, this is True, which means that the current Job will be
terminated upon error detection, corrections applied,
and restarted. In some instances, some errors may not need the job to be
terminated or may need to wait for some other event to terminate a job.
For example, a particular error may require a flag to be set to request
a job to terminate gracefully once it finishes its current task. The
handler to set the flag should be classified as is_terminating = False to
not terminate the job.

### max_num_corrections(_ = Non_ )

### *property* n_applied_corrections()

The number of times the handler has given a correction and this
has been applied.

* **Returns**

  the number of corrections applied.
* **Return type**

  (int)

### raise_on_max(_ = Fals_ )

Whether corrections from this specific handler should be applied only a
fixed maximum number of times on a single job (i.e. the counter is reset
at the beginning of each job). If the maximum number is reached the code
will either raise a MaxCorrectionsPerHandlerError (raise_on_max==True) or stops
considering the correction (raise_on_max==False). If max_num_corrections
is None this option is not considered. These options can be overridden
as class attributes of the subclass or as customizable options setting
an instance attribute from **init**.

### raises_runtime_error(_ = Tru_ )

Whether this handler causes custodian to raise a runtime error if it cannot
handle the error (i.e. if correct returns a dict with “actions”:None, or
“actions”:[])

## *class* custodian.custodian.Job()

Bases: `MSONable`

Abstract base class defining the interface for a Job.

### *property* name()

A nice string name for the job.

### *abstract* postprocess()

This method is called at the end of a job, *after* error detection.
This allows post-processing, such as cleanup, analysis of results,
etc.

### *abstract* run()

This method perform the actual work for the job. If parallel error
checking (monitoring) is desired, this must return a Popen process.

### *abstract* setup()

This method is run before the start of a job. Allows for some
pre-processing.

### terminate()

Implement termination function.

## *exception* custodian.custodian.MaxCorrectionsError(message, raises, max_errors)

Bases: `CustodianError`

Error raised when the maximum allowed number of errors is reached

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian
  * **max_errors** (*int*) – the number of errors reached

## *exception* custodian.custodian.MaxCorrectionsPerHandlerError(message, raises, max_errors_per_handler, handler)

Bases: `CustodianError`

Error raised when the maximum allowed number of errors per handler is reached

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian
  * **max_errors_per_handler** (*int*) – the number of errors per job reached
  * **handler** (*Handler*) – the handler that caused the exception

## *exception* custodian.custodian.MaxCorrectionsPerJobError(message, raises, max_errors_per_job, job)

Bases: `CustodianError`

Error raised when the maximum allowed number of errors per job is reached

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian
  * **max_errors_per_job** (*int*) – the number of errors per job reached
  * **job** (*Job*) – the job that was stopped

## *exception* custodian.custodian.NonRecoverableError(message, raises, handler)

Bases: `CustodianError`

Error raised when a handler found an error but could not fix it

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian
  * **handler** (*Handler*) – Handler that caused the exception.

## *exception* custodian.custodian.ReturnCodeError(message, raises=False)

Bases: `CustodianError`

Error raised when the process gave non zero return code

Initializes the error with a message.

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian

## *exception* custodian.custodian.ValidationError(message, raises, validator)

Bases: `CustodianError`

Error raised when a validator does not pass the check

* **Parameters**
  * **message** (*str*) – Message passed to Exception
  * **raises** (*bool*) – Whether this should be raised outside custodian
  * **validator** (*Validator*) – Validator that caused the exception.

## *class* custodian.custodian.Validator()

Bases: `MSONable`

Abstract base class defining the interface for a Validator. A Validator
differs from an ErrorHandler in that it does not correct a run and is run
only at the end of a Job. If errors are detected by a Validator, a run is
immediately terminated.

### *abstract* check()

This method is called at the end of a job.

* **Returns**

  (bool) Indicating if errors are detected.