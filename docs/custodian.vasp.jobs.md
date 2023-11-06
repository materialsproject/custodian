---
layout: default
title: custodian.vasp.jobs.md
nav_exclude: true
---

# custodian.vasp.jobs module

This module implements basic kinds of jobs for VASP runs.

## *class* custodian.vasp.jobs.GenerateVaspInputJob(input_set, contcar_only=True, \*\*kwargs)

Bases: [`Job`](custodian.custodian.md#custodian.custodian.Job)

Generates a VASP input based on an existing directory. This is typically
used to modify the VASP input files before the next VaspJob.

* **Parameters**
  * **input_set** (*str*) – Full path to the input set. E.g.,
    “pymatgen.io.vasp.sets.MPNonSCFSet”.
  * **contcar_only** (*bool*) – If True (default), only CONTCAR structures
    are used as input to the input set.

### postprocess()

Dummy postprocess.

### run()

Run the calculation.

### setup()

Dummy setup

## *class* custodian.vasp.jobs.VaspJob(vasp_cmd, output_file=’vasp.out’, stderr_file=’std_err.txt’, suffix=’’, final=True, backup=True, auto_npar=False, auto_gamma=True, settings_override=None, gamma_vasp_cmd=None, copy_magmom=False, auto_continue=False)

Bases: [`Job`](custodian.custodian.md#custodian.custodian.Job)

A basic vasp job. Just runs whatever is in the directory. But conceivably
can be a complex processing of inputs etc. with initialization.

This constructor is necessarily complex due to the need for
flexibility. For standard kinds of runs, it’s often better to use one
of the static constructors. The defaults are usually fine too.

* **Parameters**
  * **vasp_cmd** (*str*) – Command to run vasp as a list of args. For example,
    if you are using mpirun, it can be something like
    [“mpirun”, “pvasp.5.2.11”]
  * **output_file** (*str*) – Name of file to direct standard out to.
    Defaults to “vasp.out”.
  * **stderr_file** (*str*) – Name of file to direct standard error to.
    Defaults to “std_err.txt”.
  * **suffix** (*str*) – A suffix to be appended to the final output. E.g.,
    to rename all VASP output from say vasp.out to
    vasp.out.relax1, provide “.relax1” as the suffix.
  * **final** (*bool*) – Indicating whether this is the final vasp job in a
    series. Defaults to True.
  * **backup** (*bool*) – Whether to backup the initial input files. If True,
    the INCAR, KPOINTS, POSCAR and POTCAR will be copied with a
    “.orig” appended. Defaults to True.
  * **auto_npar** (*bool*) – Whether to automatically tune NPAR to be sqrt(
    number of cores) as recommended by VASP for DFT calculations.
    Generally, this results in significant speedups. Defaults to
    False. Set to False for HF, GW and RPA calculations.
  * **auto_gamma** (*bool*) – Whether to automatically check if run is a
    Gamma 1x1x1 run, and whether a Gamma optimized version of
    VASP exists with “.gamma” appended to the name of the VASP
    executable (typical setup in many systems). If so, run the
    gamma optimized version of VASP instead of regular VASP. You
    can also specify the gamma vasp command using the
    gamma_vasp_cmd argument if the command is named differently.
  * **settings_override** (*[**dict**]*) – An ansible style list of dict to
    override changes. For example, to set ISTART=1 for subsequent
    runs and to copy the CONTCAR to the POSCAR, you will provide:

  ```default
  [{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
   {"file": "CONTCAR",
    "action": {"_file_copy": {"dest": "POSCAR"}}}]
  ```

  * **gamma_vasp_cmd** (*str*) – Command for gamma vasp version when
    auto_gamma is True. Should follow the list style of
    subprocess. Defaults to None, which means “.gamma” is added
    to the last argument of the standard vasp_cmd.
  * **copy_magmom** (*bool*) – Whether to copy the final magmom from the
    OUTCAR to the next INCAR. Useful for multi-relaxation runs
    where the CHGCAR and WAVECAR are sometimes deleted (due to
    changes in fft grid, etc.). Only applies to non-final runs.
  * **auto_continue** (*bool*) – Whether to automatically continue a run
    if a STOPCAR is present. This is very useful if using the
    wall-time handler which will write a read-only STOPCAR to
    prevent VASP from deleting it once it finishes

### *classmethod* constrained_opt_run(vasp_cmd, lattice_direction, initial_strain, atom_relax=True, max_steps=20, algo=’bfgs’, \*\*vasp_job_kwargs)

Returns a generator of jobs for a constrained optimization run. Typical
use case is when you want to approximate a biaxial strain situation,
e.g., you apply a defined strain to a and b directions of the lattice,
but allows the c-direction to relax.

Some guidelines on the use of this method:
i.  It is recommended you do not use the Auto kpoint generation. The

> grid generated via Auto may fluctuate with changes in lattice
> param, resulting in numerical noise.
1. Make sure your EDIFF/EDIFFG is properly set in your INCAR. The
   optimization relies on these values to determine convergence.

* **Parameters**
  * **vasp_cmd** (*str*) – Command to run vasp as a list of args. For example,
    if you are using mpirun, it can be something like
    [“mpirun”, “pvasp.5.2.11”]
  * **lattice_direction** (*str*) – Which direction to relax. Valid values are
    “a”, “b” or “c”.
  * **initial_strain** (*float*) – An initial strain to be applied to the
    lattice_direction. This can usually be estimated as the
    negative of the strain applied in the other two directions.
    E.g., if you apply a tensile strain of 0.05 to the a and b
    directions, you can use -0.05 as a reasonable first guess for
    initial strain.
  * **atom_relax** (*bool*) – Whether to relax atomic positions.
  * **max_steps** (*int*) – The maximum number of runs. Defaults to 20 (
    highly unlikely that this limit is ever reached).
  * **algo** (*str*) – Algorithm to use to find minimum. Default is “bfgs”,
    which is fast, but can be sensitive to numerical noise
    in energy calculations. The alternative is “bisection”,
    which is more robust but can be a bit slow. The code does fall
    back on the bisection when bfgs gives a non-sensical result,
    e.g., negative lattice params.
  * **\*\*vasp_job_kwargs** – Passthrough kwargs to VaspJob. See
    `custodian.vasp.jobs.VaspJob`.
* **Returns**

  Generator of jobs. At the end of the run, an “EOS.txt” is written
  which provides a quick look at the E vs lattice parameter.

### *classmethod* double_relaxation_run(vasp_cmd, auto_npar=True, ediffg=-0.05, half_kpts_first_relax=False, auto_continue=False)

Returns a list of two jobs corresponding to an AFLOW style double
relaxation run.

* **Parameters**
  * **vasp_cmd** (*str*) – Command to run vasp as a list of args. For example,
    if you are using mpirun, it can be something like
    [“mpirun”, “pvasp.5.2.11”]
  * **auto_npar** (*bool*) – Whether to automatically tune NPAR to be sqrt(
    number of cores) as recommended by VASP for DFT calculations.
    Generally, this results in significant speedups. Defaults to
    True. Set to False for HF, GW and RPA calculations.
  * **ediffg** (*float*) – Force convergence criteria for subsequent runs (
    ignored for the initial run.)
  * **half_kpts_first_relax** (*bool*) – Whether to halve the kpoint grid
    for the first relaxation. Speeds up difficult convergence
    considerably. Defaults to False.
  * **auto_continue** (*bool*) – Whether to automatically continue a run
    if a STOPCAR is present. This is very useful if using the
    wall-time handler which will write a read-only STOPCAR to
    prevent VASP from deleting it once it finishes. Defaults to
    False.
* **Returns**

  List of two jobs corresponding to an AFLOW style run.

### *classmethod* full_opt_run(vasp_cmd, vol_change_tol=0.02, max_steps=10, ediffg=-0.05, half_kpts_first_relax=False, \*\*vasp_job_kwargs)

Returns a generator of jobs for a full optimization run. Basically,
this runs an infinite series of geometry optimization jobs until the

<!-- vol change in a particular optimization is less than vol_change_tol. -->
* **Parameters**
  * **vasp_cmd** (*str*) – Command to run vasp as a list of args. For example,
    if you are using mpirun, it can be something like
    [“mpirun”, “pvasp.5.2.11”]
  * **vol_change_tol** (*float*) – The tolerance at which to stop a run.
    Defaults to 0.05, i.e., 5%.
  * **max_steps** (*int*) – The maximum number of runs. Defaults to 10 (
    highly unlikely that this limit is ever reached).
  * **ediffg** (*float*) – Force convergence criteria for subsequent runs (
    ignored for the initial run.)
  * **half_kpts_first_relax** (*bool*) – Whether to halve the kpoint grid
    for the first relaxation. Speeds up difficult convergence
    considerably. Defaults to False.
  * **\*\*vasp_job_kwargs** – Passthrough kwargs to VaspJob. See
    `custodian.vasp.jobs.VaspJob`.
* **Returns**

  Generator of jobs.

### *classmethod* metagga_opt_run(vasp_cmd, auto_npar=True, ediffg=-0.05, half_kpts_first_relax=False, auto_continue=False)

Returns a list of thres jobs to perform an optimization for any
metaGGA functional. There is an initial calculation of the
GGA wavefunction which is fed into the initial metaGGA optimization
to precondition the electronic structure optimizer. The metaGGA
optimization is performed using the double relaxation scheme

### postprocess()

Postprocessing includes renaming and gzipping where necessary.
Also copies the magmom to the incar if necessary

### run()

Perform the actual VASP run.

* **Returns**

  (subprocess.Popen) Used for monitoring.

### setup()

Performs initial setup for VaspJob, including overriding any settings
and backing up.

### terminate()

Ensure all vasp jobs are killed.

## *class* custodian.vasp.jobs.VaspNEBJob(vasp_cmd, output_file=’neb_vasp.out’, stderr_file=’neb_std_err.txt’, suffix=’’, final=True, backup=True, auto_npar=True, half_kpts=False, auto_gamma=True, auto_continue=False, gamma_vasp_cmd=None, settings_override=None)

Bases: `VaspJob`

A NEB vasp job, especially for CI-NEB running at PBS clusters.
The class is added for the purpose of handling a different folder
arrangement in NEB calculation.

This constructor is a simplified version of VaspJob, which satisfies
the need for flexibility. For standard kinds of runs, it’s often
better to use one of the static constructors. The defaults are
usually fine too.

* **Parameters**
  * **vasp_cmd** (*str*) – Command to run vasp as a list of args. For example,
    if you are using mpirun, it can be something like
    [“mpirun”, “pvasp.5.2.11”]
  * **output_file** (*str*) – Name of file to direct standard out to.
    Defaults to “vasp.out”.
  * **stderr_file** (*str*) – Name of file to direct standard error to.
    Defaults to “std_err.txt”.
  * **suffix** (*str*) – A suffix to be appended to the final output. E.g.,
    to rename all VASP output from say vasp.out to
    vasp.out.relax1, provide “.relax1” as the suffix.
  * **final** (*bool*) – Indicating whether this is the final vasp job in a
    series. Defaults to True.
  * **backup** (*bool*) – Whether to backup the initial input files. If True,
    the INCAR, KPOINTS, POSCAR and POTCAR will be copied with a
    “.orig” appended. Defaults to True.
  * **auto_npar** (*bool*) – Whether to automatically tune NPAR to be sqrt(
    number of cores) as recommended by VASP for DFT calculations.
    Generally, this results in significant speedups. Defaults to
    True. Set to False for HF, GW and RPA calculations.
  * **half_kpts** (*bool*) – Whether to halve the kpoint grid for NEB.
    Speeds up convergence considerably. Defaults to False.
  * **auto_gamma** (*bool*) – Whether to automatically check if run is a
    Gamma 1x1x1 run, and whether a Gamma optimized version of
    VASP exists with “.gamma” appended to the name of the VASP
    executable (typical setup in many systems). If so, run the
    gamma optimized version of VASP instead of regular VASP. You
    can also specify the gamma vasp command using the
    gamma_vasp_cmd argument if the command is named differently.
  * **auto_continue** (*bool*) – Whether to automatically continue a run
    if a STOPCAR is present. This is very useful if using the
    wall-time handler which will write a read-only STOPCAR to
    prevent VASP from deleting it once it finishes.
  * **gamma_vasp_cmd** (*str*) – Command for gamma vasp version when
    auto_gamma is True. Should follow the list style of
    subprocess. Defaults to None, which means “.gamma” is added
    to the last argument of the standard vasp_cmd.
  * **settings_override** (*[**dict**]*) – An ansible style list of dict to
    override changes. For example, to set ISTART=1 for subsequent
    runs and to copy the CONTCAR to the POSCAR, you will provide:

  ```default
  [{"dict": "INCAR", "action": {"_set": {"ISTART": 1}}},
   {"file": "CONTCAR",
    "action": {"_file_copy": {"dest": "POSCAR"}}}]
  ```

### postprocess()

Postprocessing includes renaming and gzipping where necessary.

### run()

Perform the actual VASP run.

* **Returns**

  (subprocess.Popen) Used for monitoring.

### setup()

Performs initial setup for VaspNEBJob, including overriding any settings
and backing up.