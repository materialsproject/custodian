---
layout: default
title: Change Log
nav_order: 2
---

# Change Log

## 2023.10.9
* PR #293 from @samblau (#293)
    A bug was introduced during the recent Minor Q-Chem updates PR:
    ```diff
    - os.mkdir(local_scratch, exist_ok=True)
    + os.makedirs(local_scratch, exist_ok=True)
    ```
    I would appreciate it if a new version could please be released after this PR is merged. Thanks!
* PR #292 from @samblau (#292)
    This PR fixes a few bugs in the Q-Chem error handlers, adds one new handler, adds some additional tests, and slightly extends post processing scratch file handling.
* PR #285 from @janosh (#285)
    7b0c061a fix `MeshSymmetryErrorHandler` treating `ISYM=-1` as symmetry ON
    72ac1213 `PositiveEnergyErrorHandler` don't decrease `POTIM` for static calcs
* PR #284 from @janosh (#284)
    225a1e8d UnconvergedErrorHandler only set algo to normal if ISMEAR>=0
    608530b2 mv custodian/feff/tests/test_handler{,s}.py
    c11ab49e tweak bravais error handling in VaspErrorHandler
    283fe9d2 improve den-/tet error handling in case of not using kspacing
    bc022852 fix VaspErrorHandlerTest.test_bravais
* PR #283 from @janosh (#283)
    When running VASP with `INCAR` tag `kspacing` instead of a `KPOINTS` file and encountering `brmix` 2 or 3 times. Reported by @esoteric-ephemera in atomate2 r2SCAN workflow.

## v2023.7.22

- Fix for LargeSigmaHandler. Now defaults to ISMEAR=1 and fallback to ISMEAR=0 if SIGMA has been modified
  three times from 0.2 (@Andrew-S-Rosen, @janosh)
- More robust VASP job termination (@fyalcin)

## v2023.6.5

- New VASP error handler for invalid INCAR parameter (@Andrew-S-Rosen)
- Change VASP terminate function to be sensitive to execution directory (@MichaelWolloch)
- Add handler for invalid WAVECAR when going from vasp_gam to vasp_std (@Andrew-S-Rosen)

## v2023.5.12

- Add back kwargs to VaspHandler to maintain backward compatibility (@Andrew-S-Rosen)

## v2023.5.7

- VASP Handler: Better error checking for too_few_nbands (@Andrew-S-Rosen)
- VASP Handler: General clean up and mitigating unnecessary INCAR swaps (@Andrew-S-Rosen)
- VASP Handler: Remove deprecated handlers and kwargs (@Andrew-S-Rosen)
- VASP Handler: Add a new correction for the ZPOTRF ZTRTRI error that is specific to small structures (@Andrew-S-Rosen)
- VASP Handler: Add a new handler for the SET_CORE_WF error (@Andrew-S-Rosen)
- VASP Handler: Only apply the algo_tet handler if SCF convergence failed (@Andrew-S-Rosen)
- VASP Handler: AMIN handler should only be applied if SCF is not converged (@Andrew-S-Rosen)
- VASP Handler: Do not set ADDGRID to True (@Andrew-S-Rosen)

## v2023.3.8

- Updates for QChem6 support (@samblau)
- Updates for CP2K support (@nwinner)

## v2022.5.26

- PR #219 from @samblau. Q-Chem updates to NBO, new geometry optimizer, revamped SCF error handling.

## v2022.5.17

- PR #220 from @yury-lysogorskiy. Fix for NBANDS when NBANDS is very small.
- PR #211 from @Andrew-S-Rosen. Handler for error in reading plane wave coeff.
- PR #214 from @Andrew-S-Rosen. Handler for `ZHEGV` error by reducing number of cores.
- PR #215 from @Andrew-S-Rosen. Fix for new `ZPOTRF` error phrasing.
- PR #210 from @nwinner. CP2K support.

## v2022.2.13

- Support for new Lobster versions (@naik-aakash)
- Bug fix for termination of gamma VASP runs.

## v2022.1.17

- New NBANDS not sufficient handler in VASP (@Andrew-S-Rosen)
- New VASP error handling for VASP 6.2.1 HNFORM error (@Andrew-S-Rosen)
- Improve zbrent handler by trying to get IBRION = 2 to succeed before switching to IBRION = 1 (@Andrew-S-Rosen)
- Updates to ALGO handling with grad_not_orth and algo_tet (@Andrew-S-Rosen)

## v2021.12.2

- Address new VASP6 inconsistent Bravais lattice error (@Andrew-S-Rosen)
- Don't check for drift if NSW = 1 (@Andrew-S-Rosen)
- [VASP] Switch from IBRION = 1 --> 2 if the BRIONS error occurs more than once (@Andrew-S-Rosen)
- Handle finite difference ncore error (@utf)
- [VASP] More robust zbrent fix (@Andrew-S-Rosen)
- [VASP] Increase posmap error count (@Andrew-S-Rosen)
- [VASP] Update real_optlay logic to avoid LREAL = True (@Andrew-S-Rosen)
- [VASP] More appropriate grad_not_orth fix and new algo_tet error handler (@Andrew-S-Rosen)
- [VASP] Adjust SCF Ladder for meta-GGAs/hybrids (@Andrew-S-Rosen)
- Refactor VaspErrorHandler.check() (@janosh)
- Fix VaspErrorHandler not handling "tetrahedron method fails" (@janosh)

## v2021.2.8

- Allow static calculations with ISMEAR = -5 for metals (@MichaelWolloch).

## v2021.1.8

- New handlers for VASP6 (@mkhorton, @rkingsbury)

## v2021.1.7

- Improved handling of scratch directories and update for QChem.

## v2019.8.24

- Cleanup codestyle, which is now enforced.
- Py3k support only, in line with pymatgen.
- Update dependencies.
- Sentry support (@mkhorton).
- Complete qchem overhaul (frequency flattening optimization, refined error
  handlers) (@samblau)

## v2019.2.10

- Improved slow convergence handling. (@shyamd)

## v2019.2.7

- Improved error logging.
- Improved handling of frozen jobs and potim errors.
- Improved Exceptino handling. (Guido Petretto)

## v2017.12.23

- cstdn command line tool is now official with docs.
- Fine-grained control of VaspErrorHandler is now possible using
  `errors_subset_to_catch`.
- Switched to date-based versioning for custodian like pymatgen.

## v1.1.1

- DriftErrorHandler (Shyam)

## v1.1.0

- Improved error handling for Qchem calculations.

## v1.0.4

- Improved handling of non-zero return codes.

## v1.0.2

- Interrupted run feature. (Shyam Dwaraknath)

## v1.0.1

- Pymatgen 4.0.0 compatible release.

## v1.0.0

- Custodian now comes with a "cstdn" script that enables the arbitrary creation
  of simple job sequences using a yaml file, and the running of calculations
  based on these yaml specifications.

## v0.8.8

1. Fix setup.py.

## v0.8.5

1. Refactoring to support pymatgen 3.1.4.

## v0.8.2

1. Made auto_npar optional for double relaxation VASP run.

## v0.8.1

1. Misc bug fixes (minor).

## v0.8.0

1. Major refactoring of Custodian to introdce Validators,
   which are effectively post-Job checking mechanisms that do not perform
   error correction.
2. **Backwards incompatibility** BadVasprunXMLHandler is now a validator,
   which must be separately imported to be used.
3. Miscellaneous cleanup of Py3k fixes.

## v0.7.6

1. Custodian is now Python 3 compatible and uses the latest versions of
   pymatgen and monty.

## v0.7.5

1. **Major** Custodian now exits with RuntimeError when max_errors or
   unrecoverable_error is encountered.
2. Added BadVasprunXMLHandler.

## v0.7.4

1. auto_npar option in VaspJob now properly handles Hessian calculations.
2. WalltimeHandler now supports termination at electronic step (David
   Waroquiers).
3. Improved handling of BRMIX fixes.

## v0.7.3

1. Improved backwards compatibility for WallTimeHandler.
2. Improvements to VaspErrorHandler. No longer catches spurious BRMIX error
   messages when NELECT is specified in INCAR, and pricel and rot_mat errors
   are now fixed with symmetry precision and gamma centered KPOINTS instead.
3. Improved Qchem error handler (Xiaohui Qu).

## v0.7.2

1. Improved WalltimeHandler (PBSWalltimeHandler is a subset and is now
   deprecated).
2. New monty required version (>= 0.2.2).

## v0.7.1

1. Much improved qchem error handling (Xiaohui Qu).
2. New Monty required version (>= 0.2.0).

## v0.7.0

1. \*\*Backwards incompatible with v0.6.3. Refactoring to move commonly used
   Python utility functions to `Monty package <https://pypi.python
.org/pypi/monty>`\_, which is now a depedency
   for custodian.
2. Custodian now requires pymatgen >= 2.9.0 for VASP, Qchem and Nwchem jobs
   and handlers.
3. converge_kpoints script now has increment mode.
4. ErrorHandlers now have a new API, where the class variables "is_monitor"
   and "is_terminating" are provided to indicate if a particular handler
   runs in the background during a Job and whether a handler should
   terminate the job. Some errors may not be critical or may need to wait
   for some other event to terminate a job. For example,
   a particular error may require a flag to be set to request a job to
   terminate gracefully once it finishes its current task. The handler to
   set the flag should not terminate the job.

## v0.6.3

1. Added buffer time option in PBSWalltimeHandler.
2. Improved Qchem jobs and handlers (Xiaohui Qu).
3. Vastly improved API docs.

## v0.6.2

1. Bug fix release to support sub dirs in run folder when using scratch.
2. Improve handling of walltime in PBSWalltimeHander.

## v0.6.1

1. Bug fix release to address minor issue with checkpointing.
2. Checkpointing is now turned off by default.

## v0.6.0

1. Checkpointing implemented for Custodian. Custodian can now checkpoint all
   files in the current working directory after every successful job. If the
   job is resubmitted, it will restore files and start from the last
   checkpoint. Particularly useful for multi-job runs.
2. Added PBSWalltimeHandler to handle wall times for PBS Vasp Jobs.
3. Qchem error handlers and jobs.

## v0.5.0

1. Added scratch_dir option to Custodian class as well as run_vasp and
   run_nwchem scripts. Many supercomputing clusters have a scratch space
   which have significantly faster IO. This option provides a transparent way
   to specify the jobs to be performed in the scratch. Especially useful for
   jobs which have significant file IO.

## v0.4.5

1. Fix gzip of output.

## v0.4.3

1. Added handling for ZBRENT error for VASP.
2. Minor refactoring to consolidate backup and gzip directory methods.

## v0.4.2

1. Rudimentary support for Nwchem error handling (by Shyue Ping Ong).
2. Improved VASP error handling (by Steve Dacek and Will Richards).

## v0.4.1

1. Added hanlding of PRICEL error in VASP.
2. Speed and robustness improvements.
3. BRIONS error now handled by changing ISYM.

## v0.4.0

1. Many VASP handlers are now consolidated into a single VaspErrorHandler.
2. Many more fixes for VASP runs, including the "TOO FEW BANDS",
   "TRIPLE PRODUCT", "DENTET" and "BRIONS" errors.
3. VaspJob now includes the auto_npar and auto_gamma options, which
   automatically optimizes the NPAR setting to be sqrt(number of cores) as
   per the VASP recommendation for DFT runs and tries to search for a
   gamma-only compiled version of VASP for gamma 1x1x1 runs.

## v0.3.5

1. Bug fix for incorrect shift error handler in VASP.
2. More robust fix for unconverged VASP runs (switching from ALGO fast to
   normal).
3. Expanded documentation.

## v0.3.4

1. Added support for handlers that perform monitor a job as it is progressing
   and terminates it if necessary. Useful for correcting errors that come up
   by do not cause immediate job failures.

## v0.3.2

1. Important bug fix for VaspJob and converge_kpoints script.

## v0.3.0

1. Major update to custodian API. Custodian now perform more comprehensive
   logging in a file called custodian.json, which logs all jobs and
   corrections performed.

## v0.2.6

1. Bug fix for run_vasp script for static runs.

## v0.2.5

1. run_vasp script that now provides flexible specification of vasp runs.
2. Vastly improved error handling for VASP runs.
3. Improved logging system for custodian.
4. Improved API for custodian return types during run.
5. First stable release.

## v0.2.4

1. Bug fixes for aflow style runs assimilation.
