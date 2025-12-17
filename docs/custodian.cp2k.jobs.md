---
layout: default
title: custodian.cp2k.jobs.md
nav_exclude: true
---

# custodian.cp2k.jobs module

This module implements basic kinds of jobs for Cp2k runs.

## *class* custodian.cp2k.jobs.Cp2kJob(cp2k_cmd, input_file=’cp2k.inp’, output_file=’cp2k.out’, stderr_file=’std_err.txt’, suffix=’’, final=True, backup=True, settings_override=None, restart=False)

Bases: [`Job`](custodian.custodian.md#custodian.custodian.Job)

A basic cp2k job. Just runs whatever is in the directory. But conceivably
can be a complex processing of inputs etc. with initialization.

This constructor is necessarily complex due to the need for
flexibility. For standard kinds of runs, it’s often better to use one
of the static constructors. The defaults are usually fine too.

* **Parameters**
  * **cp2k_cmd** (*list*) – Command to run cp2k as a list of args. For example,
    if you are using mpirun, it can be something like
    [“mpirun”, “cp2k.popt”]
  * **input_file** (*str*) – Name of the file to use as input to CP2K
    executable. Defaults to “cp2k.inp”
  * **output_file** (*str*) – Name of file to direct standard out to.
    Defaults to “cp2k.out”.
  * **stderr_file** (*str*) – Name of file to direct standard error to.
    Defaults to “std_err.txt”.
  * **suffix** (*str*) – A suffix to be appended to the final output. E.g.,
    to rename all CP2K output from say cp2k.out to
    cp2k.out.relax1, provide “.relax1” as the suffix.
  * **final** (*bool*) – Indicating whether this is the final cp2k job in a
    series. Defaults to True.
  * **backup** (*bool*) – Whether to backup the initial input files. If True,
    the input file will be copied with a
    “.orig” appended. Defaults to True.
  * **settings_override** (     *[**actions**]*) – A list of actions. See the Cp2kModder
    in interpreter.py
  * **restart** (*bool*) – Whether to run in restart mode, i.e. this a continuation of
    a previous calculation. Default is False.

### *classmethod* double_job(cp2k_cmd, input_file=’cp2k.inp’, output_file=’cp2k.out’, stderr_file=’std_err.txt’, backup=True)

This creates a sequence of two jobs. The first of which is an “initialization” of the
wfn. Using this, the “restart” function can be exploited to determine if a diagonalization
job can/would benefit from switching to OT scheme. If not, then the second job remains a
diagonalization job, and there is minimal overhead from restarting.

### *classmethod* gga_static_to_hybrid(cp2k_cmd, input_file=’cp2k.inp’, output_file=’cp2k.out’, stderr_file=’std_err.txt’, backup=True, settings_override_gga=None, settings_override_hybrid=None)

A bare gga to hybrid calculation. Removes all unnecessary features
from the gga run, and making it only a ENERGY/ENERGY_FORCE
depending on the hybrid run.

### postprocess()

Postprocessing includes renaming and gzipping where necessary.

### *classmethod* pre_screen_hybrid(cp2k_cmd, input_file=’cp2k.inp’, output_file=’cp2k.out’, stderr_file=’std_err.txt’, backup=True)

Build a job where the first job is an unscreened hybrid static calculation, then the second one
uses the wfn from the first job as a restart to do a screened calculation.

### run()

Perform the actual CP2K run.

* **Returns**

  (subprocess.Popen) Used for monitoring.

### setup()

Performs initial setup for Cp2k in three stages. First, if custodian is running in restart mode, then
the restart function will copy the restart file to self.input_file, and remove any previous WFN initialization
if present. Second, any additional user specified settings will be applied. Lastly, a backup of the input
file will be made for reference.

### terminate()

Terminate cp2k