---
layout: default
title: custodian.vasp.handlers.md
nav_exclude: true
---

# custodian.vasp.handlers module

This module implements specific error handlers for VASP runs. These handlers
try to detect common errors in vasp runs and attempt to fix them on the fly
by modifying the input files.


### _class_ custodian.vasp.handlers.AliasingErrorHandler(output_filename='vasp.out')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Master VaspErrorHandler class that handles a number of common errors
that occur during VASP runs.

Initializes the handler with the output file to check.


* **Parameters**

    **output_filename** (*str*) – This is the file where the stdout for vasp
    is being redirected. The error messages that are checked are
    present in the stdout. Defaults to “vasp.out”, which is the
    default redirect used by [`custodian.vasp.jobs.VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob).



#### check()
Check for error.


#### correct()
Perform corrections.


#### error_msgs(_ = {'aliasing': ['WARNING: small aliasing (wrap around) errors must be expected'], 'aliasing_incar': ['Your FFT grids (NGX,NGY,NGZ) are not sufficient for an accurate']_ )

#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.CheckpointHandler(interval=3600)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

This is not an error handler per se, but rather a checkpointer. What this
does is that every X seconds, a STOPCAR and CHKPT will be written. This
forces VASP to stop at the end of the next ionic step. The files are then
copied into a subdir, and then the job is restarted. To use this proper,
max_errors in Custodian must be set to a very high value, and you
probably wouldn’t want to use any standard VASP error handlers. The
checkpoint will be stored in subdirs chk_#. This should be used in
combination with the StoppedRunHandler.

Initializes the handler with an interval.


* **Parameters**


    * **interval** (*int*) – Interval at which to checkpoint in seconds.


    * **3600** (*Defaults to*) –



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


#### is_terminating(_ = Fals_ )
Whether this handler terminates a job upon error detection. By
default, this is True, which means that the current Job will be
terminated upon error detection, corrections applied,
and restarted. In some instances, some errors may not need the job to be
terminated or may need to wait for some other event to terminate a job.
For example, a particular error may require a flag to be set to request
a job to terminate gracefully once it finishes its current task. The
handler to set the flag should be classified as is_terminating = False to
not terminate the job.


### _class_ custodian.vasp.handlers.DriftErrorHandler(max_drift=None, to_average=3, enaug_multiply=2)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Corrects for total drift exceeding the force convergence criteria.

Initializes the handler with max drift
:param max_drift: This defines the max drift. Leaving this at the default of None gets the max_drift from

> EDFIFFG


#### check()
Check for error.


#### correct()
Perform corrections.


### _class_ custodian.vasp.handlers.FrozenJobErrorHandler(output_filename='vasp.out', timeout=21600)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Detects an error when the output file has not been updated
in timeout seconds. Changes ALGO to Normal from Fast

Initializes the handler with the output file to check.


* **Parameters**


    * **output_filename** (*str*) – This is the file where the stdout for vasp
    is being redirected. The error messages that are checked are
    present in the stdout. Defaults to “vasp.out”, which is the
    default redirect used by [`custodian.vasp.jobs.VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob).


    * **timeout** (*int*) – The time in seconds between checks where if there
    is no activity on the output file, the run is considered
    frozen. Defaults to 3600 seconds, i.e., 1 hour.



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.IncorrectSmearingHandler(output_filename='vasprun.xml')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a calculation is a metal (zero bandgap), has been run with
ISMEAR=-5, and is not a static calculation, which is only appropriate for
semiconductors. If this occurs, this handler will rerun the calculation
using the smearing settings appropriate for metals (ISMEAR=2, SIGMA=0.2).

Initializes the handler with the output file to check.


* **Parameters**

    **output_filename** (*str*) – Filename for the vasprun.xml file. Change
    this only if it is different from the default (unlikely).



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Fals_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.LargeSigmaHandler()
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

When ISMEAR > 0 (Methfessel-Paxton), monitor the magnitude of the entropy
term T\*S in the OUTCAR file. If the entropy term is larger than 1 meV/atom, reduce the
value of SIGMA. See VASP documentation for ISMEAR.

Initializes the handler with a buffer time.


#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.LrfCommutatorHandler(output_filename='std_err.txt')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Corrects LRF_COMMUTATOR errors by setting LPEAD=True if not already set.
Note that switching LPEAD=T can slightly change results versus the
default due to numerical evaluation of derivatives.

Initializes the handler with the output file to check.


* **Parameters**

    **output_filename** (*str*) – This is the file where the stderr for vasp
    is being redirected. The error messages that are checked are
    present in the stderr. Defaults to “std_err.txt”, which is the
    default redirect used by [`custodian.vasp.jobs.VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob).



#### check()
Check for error.


#### correct()
Perform corrections.


#### error_msgs(_ = {'lrf_comm': ['LRF_COMMUTATOR internal error']_ )

#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.MeshSymmetryErrorHandler(output_filename='vasp.out', output_vasprun='vasprun.xml')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Corrects the mesh symmetry error in VASP. This error is sometimes
non-fatal. So this error handler only checks at the end of the run,
and if the run has converged, no error is recorded.

Initializes the handler with the output files to check.


* **Parameters**


    * **output_filename** (*str*) – This is the file where the stdout for vasp
    is being redirected. The error messages that are checked are
    present in the stdout. Defaults to “vasp.out”, which is the
    default redirect used by [`custodian.vasp.jobs.VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob).


    * **output_vasprun** (*str*) – Filename for the vasprun.xml file. Change
    this only if it is different from the default (unlikely).



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Fals_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.NonConvergingErrorHandler(output_filename='OSZICAR', nionic_steps=10)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a run is hitting the maximum number of electronic steps at the
last nionic_steps ionic steps (default=10). If so, change ALGO using a
multi-step ladder scheme or kill the job.

Initializes the handler with the output file to check.


* **Parameters**


    * **output_filename** (*str*) – This is the OSZICAR file. Change
    this only if it is different from the default (unlikely).


    * **nionic_steps** (*int*) – The threshold number of ionic steps that
    needs to hit the maximum number of electronic steps for the
    run to be considered non-converging.



#### check()
Check for error.


#### correct()
Perform corrections.


#### _classmethod_ from_dict(d)
Custom from_dict method to preserve backwards compatibility with
older versions of Custodian.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.PositiveEnergyErrorHandler(output_filename='OSZICAR')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a run has positive absolute energy.
If so, change ALGO from Fast to Normal or kill the job.

Initializes the handler with the output file to check.


* **Parameters**

    **output_filename** (*str*) – This is the OSZICAR file. Change
    this only if it is different from the default (unlikely).



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.PotimErrorHandler(input_filename='POSCAR', output_filename='OSZICAR', dE_threshold=1)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a run has excessively large positive energy changes.
This is typically caused by too large a POTIM. Runs typically
end up crashing with some other error (e.g. BRMIX) as the geometry
gets progressively worse.

Initializes the handler with the input and output files to check.


* **Parameters**


    * **input_filename** (*str*) – This is the POSCAR file that the run
    started from. Defaults to “POSCAR”. Change
    this only if it is different from the default (unlikely).


    * **output_filename** (*str*) – This is the OSZICAR file. Change
    this only if it is different from the default (unlikely).


    * **dE_threshold** (*float*) – The threshold energy change. Defaults to 1eV.



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.ScanMetalHandler(output_filename='vasprun.xml')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a SCAN calculation is a metal (zero bandgap) but has been run with
a KSPACING value appropriate for semiconductors. If this occurs, this handler
will rerun the calculation using the KSPACING setting appropriate for metals
(KSPACING=0.22). Note that this handler depends on values set in MPScanRelaxSet.

Initializes the handler with the output file to check.


* **Parameters**

    **output_filename** (*str*) – Filename for the vasprun.xml file. Change
    this only if it is different from the default (unlikely).



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Fals_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.StdErrHandler(output_filename='std_err.txt')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Master StdErr class that handles a number of common errors
that occur during VASP runs with error messages only in
the standard error.

Initializes the handler with the output file to check.


* **Parameters**

    **output_filename** (*str*) – This is the file where the stderr for vasp
    is being redirected. The error messages that are checked are
    present in the stderr. Defaults to “std_err.txt”, which is the
    default redirect used by [`custodian.vasp.jobs.VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob).



#### check()
Check for error.


#### correct()
Perform corrections.


#### error_msgs(_ = {'kpoints_trans': ['internal error in GENERATE_KPOINTS_TRANS: number of G-vector changed in star'], 'out_of_memory': ['Allocation would exceed memory limit']_ )

#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.StoppedRunHandler()
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

This is not an error handler per se, but rather a checkpointer. What this
does is that every X seconds, a STOPCAR will be written. This forces VASP to
stop at the end of the next ionic step. The files are then copied into a
subdir, and then the job is restarted. To use this proper, max_errors in
Custodian must be set to a very high value, and you probably wouldn’t
want to use any standard VASP error handlers. The checkpoint will be
stored in subdirs chk_#. This should be used in combination with the
StoppedRunHandler.

Dummy init.


#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Fals_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


#### is_terminating(_ = Fals_ )
Whether this handler terminates a job upon error detection. By
default, this is True, which means that the current Job will be
terminated upon error detection, corrections applied,
and restarted. In some instances, some errors may not need the job to be
terminated or may need to wait for some other event to terminate a job.
For example, a particular error may require a flag to be set to request
a job to terminate gracefully once it finishes its current task. The
handler to set the flag should be classified as is_terminating = False to
not terminate the job.


### _class_ custodian.vasp.handlers.UnconvergedErrorHandler(output_filename='vasprun.xml')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a run is converged.

Initializes the handler with the output file to check.


* **Parameters**

    **output_vasprun** (*str*) – Filename for the vasprun.xml file. Change
    this only if it is different from the default (unlikely).



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Fals_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.VaspErrorHandler(output_filename='vasp.out', natoms_large_cell=None, errors_subset_to_catch=None, vtst_fixes=False)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Master VaspErrorHandler class that handles a number of common errors
that occur during VASP runs.

Initializes the handler with the output file to check.


* **Parameters**


    * **output_filename** (*str*) – This is the file where the stdout for vasp
    is being redirected. The error messages that are checked are
    present in the stdout. Defaults to “vasp.out”, which is the
    default redirect used by [`custodian.vasp.jobs.VaspJob`](custodian.vasp.jobs.md#custodian.vasp.jobs.VaspJob).


    * **natoms_large_cell** (*int*) – Number of atoms threshold to treat cell
    as large. Affects the correction of certain errors. Defaults to
    None (not used). Deprecated.


    * **errors_subset_to_detect** (*list*) – A subset of errors to catch. The
    default is None, which means all supported errors are detected.
    Use this to only catch only a subset of supported errors.
    E.g., [“eddrrm”, “zheev”] will only catch the eddrmm and zheev
    errors, and not others. If you wish to only excluded one or
    two of the errors, you can create this list by the following
    lines:


    * **vtst_fixes** (*bool*) – Whether to consider VTST optimizers. Defaults to
    False for compatibility purposes.



    ```
    ``
    ```

    \`
    subset = list(VaspErrorHandler.error_msgs.keys())
    subset.pop(“eddrrm”)

    handler = VaspErrorHandler(errors_subset_to_catch=subset)


    ```
    ``
    ```



    ```
    `
    ```





#### check()
Check for error.


#### correct()
Perform corrections.


#### error_msgs(_ = {'algo_tet': ['ALGO=A and IALGO=5X tend to fail'], 'amin': ['One of the lattice vectors is very long (>50 A), but AMIN'], 'bravais': ['Inconsistent Bravais lattice'], 'brions': ['BRIONS problems: POTIM should be increased'], 'brmix': ['BRMIX: very serious problems'], 'coef': ['while reading plane'], 'dentet': ['DENTET'], 'dfpt_ncore': ['PEAD routines do not work for NCORE', 'remove the tag NPAR from the INCAR file'], 'edddav': ['Error EDDDAV: Call to ZHEGV failed'], 'eddrmm': ['WARNING in EDDRMM: call to ZHEGV failed'], 'elf_kpar': ['ELF: KPAR>1 not implemented'], 'elf_ncl': ['WARNING: ELF not implemented for non collinear case'], 'grad_not_orth': ['EDWAV: internal error, the gradient is not orthogonal'], 'hnform': ['HNFORM: k-point generating'], 'incorrect_shift': ['Could not get correct shifts'], 'inv_rot_mat': ['rotation matrix was not found (increase SYMPREC)'], 'nbands_not_sufficient': ['number of bands is not sufficient'], 'nicht_konv': ['ERROR: SBESSELITER : nicht konvergent'], 'point_group': ['group operation missing'], 'posmap': ['POSMAP'], 'pricel': ['internal error in subroutine PRICEL'], 'pssyevx': ['ERROR in subspace rotation PSSYEVX'], 'real_optlay': ['REAL_OPTLAY: internal error', 'REAL_OPT: internal ERROR'], 'rhosyg': ['RHOSYG'], 'rot_matrix': ['Found some non-integer element in rotation matrix', 'SGRCON'], 'rspher': ['ERROR RSPHER'], 'subspacematrix': ['WARNING: Sub-Space-Matrix is not hermitian in DAV'], 'symprec_noise': ['determination of the symmetry of your systems shows a strong'], 'tet': ['Tetrahedron method fails', 'tetrahedron method fails', 'Fatal error detecting k-mesh', 'Fatal error: unable to match k-point', 'Routine TETIRR needs special values', 'Tetrahedron method fails (number of k-points < 4)', 'BZINTS'], 'tetirr': ['Routine TETIRR needs special values'], 'too_few_bands': ['TOO FEW BANDS'], 'triple_product': ['ERROR: the triple product of the basis vectors'], 'zbrent': ['ZBRENT: fatal internal in', 'ZBRENT: fatal error in bracketing'], 'zheev': ['ERROR EDDIAG: Call to routine ZHEEV failed!'], 'zpotrf': ['LAPACK: Routine ZPOTRF failed', 'Routine ZPOTRF ZTRTRI']_ )

#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


### _class_ custodian.vasp.handlers.WalltimeHandler(wall_time=None, buffer_time=300, electronic_step_stop=False)
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Check if a run is nearing the walltime. If so, write a STOPCAR with
LSTOP or LABORT = .True.. You can specify the walltime either in the init (
which is unfortunately necessary for SGE and SLURM systems. If you happen
to be running on a PBS system and the PBS_WALLTIME variable is in the run
environment, the wall time will be automatically determined if not set.

Initializes the handler with a buffer time.


* **Parameters**


    * **wall_time** (*int*) – Total walltime in seconds. If this is None and
    the job is running on a PBS system, the handler will attempt to
    determine the walltime from the PBS_WALLTIME environment
    variable. If the wall time cannot be determined or is not
    set, this handler will have no effect.


    * **buffer_time** (*int*) – The min amount of buffer time in secs at the
    end that the STOPCAR will be written. The STOPCAR is written
    when the time remaining is < the higher of 3 x the average
    time for each ionic step and the buffer time. Defaults to
    300 secs, which is the default polling time of Custodian.
    This is typically sufficient for the current ionic step to
    complete. But if other operations are being performed after
    the run has stopped, the buffer time may need to be increased
    accordingly.


    * **electronic_step_stop** (*bool*) – Whether to check for electronic steps
    instead of ionic steps (e.g. for static runs on large systems or
    static HSE runs, …). Be careful that results such as density
    or wavefunctions might not be converged at the electronic level.
    Should be used with LWAVE = .True. to be useful. If this is
    True, the STOPCAR is written with LABORT = .TRUE. instead of
    LSTOP = .TRUE.



#### check()
Check for error.


#### correct()
Perform corrections.


#### is_monitor(_ = Tru_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.


#### is_terminating(_ = Fals_ )
Whether this handler terminates a job upon error detection. By
default, this is True, which means that the current Job will be
terminated upon error detection, corrections applied,
and restarted. In some instances, some errors may not need the job to be
terminated or may need to wait for some other event to terminate a job.
For example, a particular error may require a flag to be set to request
a job to terminate gracefully once it finishes its current task. The
handler to set the flag should be classified as is_terminating = False to
not terminate the job.


#### raises_runtime_error(_ = Fals_ )
Whether this handler causes custodian to raise a runtime error if it cannot
handle the error (i.e. if correct returns a dict with “actions”:None, or
“actions”:[])