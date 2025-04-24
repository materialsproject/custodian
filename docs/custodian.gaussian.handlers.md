---
layout: default
title: custodian.gaussian.handlers.md
nav_exclude: true
---

# custodian.gaussian.handlers module

This module implements error handlers for Gaussian runs.

## *class* custodian.gaussian.handlers.GaussianErrorHandler(input_file: str, output_file: str, stderr_file: str = ‘stderr.txt’, cart_coords: bool = True, scf_max_cycles: int = 100, opt_max_cycles: int = 100, job_type: str = ‘normal’, lower_functional: str | None = None, lower_basis_set: str | None = None, prefix: str = ‘error’, check_convergence: bool = True)

Bases: `ErrorHandler`

Master GaussianErrorHandler class that handles a number of common errors that occur
during Gaussian runs.

Initialize the GaussianErrorHandler class.

* **Parameters:**
  * **input_file** (*str*) – The name of the input file for the Gaussian job.
  * **output_file** (*str*) – The name of the output file for the Gaussian job.
  * **stderr_file** (*str*) – The name of the standard error file for the Gaussian job.
    Defaults to ‘stderr.txt’.
  * **cart_coords** (*bool*) – Whether the coordinates are in cartesian format.
    Defaults to True.
  * **scf_max_cycles** (*int*) – The maximum number of SCF cycles. Defaults to 100.
  * **opt_max_cycles** (*int*) – The maximum number of optimization cycles. Defaults to
    100.
  * **job_type** (*str*) – The type of job to run. Supported options are ‘normal’ and
    ‘better_guess’. Defaults to ‘normal’. If ‘better_guess’ is chosen, the
    job will be rerun at a lower level of theory to get a better initial
    guess of molecular orbitals or geometry, if needed.
  * **lower_functional** (*str*) – The lower level of theory to use for a better guess.
  * **lower_basis_set** (*str*) – The lower basis set to use for a better guess.
  * **prefix** (*str*) – The prefix to use for the backup files. Defaults to error,
    which means a series of error.1.tar.gz, error.2.tar.gz, … will be
    generated.
  * **check_convergence** (*bool*) – Whether to check for convergence during an
    optimization job. Defaults to True. If True, the convergence data will
    be monitored and plotted (convergence criteria versus cycle number) and
    saved to a file called ‘convergence.png’.

### GRID_NAMES  *= (‘finegrid’, ‘fine’, ‘superfinegrid’, ‘superfine’, ‘coarsegrid’, ‘coarse’, ‘sg1grid’, ‘sg1’, ‘pass0grid’, ‘pass0’)*

### MEM_UNITS  *= (‘kb’, ‘mb’, ‘gb’, ‘tb’, ‘kw’, ‘mw’, ‘gw’, ‘tw’)*

### activate_better_guess  *= False*

### check(directory: str = ‘./’)

Check for errors in the Gaussian output file.

### conv_criteria\*: ClassVar\*  *= {‘max_disp’: re.compile(’\\s+(Maximum Displacement)\\s+(-?\\d+.?\\d\*|.\*)\\s+(-?\\d+.?\\d\*)’), ‘max_force’: re.compile(’\\s+(Maximum Force)\\s+(-?\\d+.?\\d\*|.\*)\\s+(-?\\d+.?\\d\*)’), ‘rms_disp’: re.compile(’\\s+(RMS {5}Displacement)\\s+(-?\\d+.?\\d\*|.\*)\\s+(-?\\d+.?\\d\*)’), ‘rms_force’: re.compile(’\\s+(RMS {5}Force)\\s+(-?\\d+.?\\d\*|.\*)\\s+(-?\\d+.?\\d\*)’)}*

### *static* convert_mem(mem: float, unit: str)

Convert memory size between different units to megabytes (MB).

* **Parameters:**
  * **mem** (*float*) – The memory size to convert.
  * **unit** (*str*) – The unit of the input memory size. Supported units include
    ‘kb’, ‘mb’, ‘gb’, ‘tb’, and word units (‘kw’, ‘mw’, ‘gw’, ‘tw’), or an
    empty string for default conversion (from words).
* **Returns:**
  The memory size in MB.
* **Return type:**
  float

### correct(directory: str = ‘./’)

Perform necessary actions to correct the errors in the Gaussian output.

### error_defs\*: ClassVar\*  *= {‘A syntax error was detected in the input line.’: ‘syntax’, ‘Atom specifications unexpectedly found in input stream.’: ‘found_coords’, ‘Bad file opened by FileIO’: ‘bad_file’, ‘Convergence failure’: ‘scf_convergence’, ‘End of file in ZSymb’: ‘zmatrix’, ‘End of file reading connectivity.’: ‘coords’, ‘Error in internal coordinate system’: ‘internal_coords’, ‘FileIO operation on non-existent file.’: ‘missing_file’, ‘FormBX had a problem’: ‘linear_bend’, ‘Inv3 failed in PCMMkU’: ‘solute_solvent_surface’, ‘Linear angle in Tors.’: ‘linear_bend’, ‘No data on chk file.’: ‘empty_file’, ‘Optimization stopped’: ‘opt_steps’, ‘Out-of-memory error in routine’: ‘insufficient_mem’, ‘The combination of multiplicity ([0-9]+) and \\s+? ([0-9]+) electrons is impossible.’: ‘charge’, ‘There are no atoms in this input structure !’: ‘missing_mol’, ‘Z-matrix optimization but no Z-matrix variables.’: ‘coord_inputs’}*

### error_patt  *= re.compile(‘Optimization stopped|Convergence failure|FormBX had a problem|Linear angle in Tors.|Inv3 failed in PCMMkU|Error in internal coordinate system|End of file in ZSymb|There are no atoms in this input str)*

### grid_patt  *= re.compile(‘(-?\\d{5})’)*

### recom_mem_patt  *= re.compile(‘Use %mem=([0-9]+)MW to provide the minimum amount of memory required to complete this step.’)*

## *class* custodian.gaussian.handlers.WallTimeErrorHandler(wall_time: int, buffer_time: int, input_file: str, output_file: str, stderr_file: str = ‘stderr.txt’, prefix: str = ‘error’)

Bases: `ErrorHandler`

Check if a run is nearing the walltime. If so, terminate the job and restart from
the last .rwf file. A job is considered to be nearing the walltime if the remaining
time is less than or equal to the buffer time.

Initialize the WalTimeErrorHandler class.

* **Parameters:**
  * **wall_time** (*int*) – The total wall time for the job in seconds.
  * **buffer_time** (*int*) – The buffer time in seconds. If the remaining time is less
    than or equal to the buffer time, the job is considered to be nearing the
    walltime and will be terminated.
  * **input_file** (*str*) – The name of the input file for the Gaussian job.
  * **output_file** (*str*) – The name of the output file for the Gaussian job.
  * **stderr_file** (*str*) – The name of the standard error file for the Gaussian job.
    Defaults to ‘stderr.txt’.
  * **prefix** (*str*) – The prefix to use for the backup files. Defaults to error,
    which means a series of error.1.tar.gz, error.2.tar.gz, … will be
    generated.

### check(directory: str = ‘./’)

Check if the job is nearing the walltime. If so, return True, else False.

### correct(directory: str = ‘./’)

Perform the corrections.

### is_monitor\*: bool\*  *= True*

This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.