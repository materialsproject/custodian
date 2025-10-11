---
layout: default
title: Change Log
nav_order: 2
---

# Change Log

## 2025.10.11
* PR #404 from @NicoPhase (#404)
    This is a fix to issue #403. It makes sure that backup files aren't overwritten when a series of custodian jobs are executed in the same folder. The fix is achieved by taking both .tar.gz and .tar files into account when determining the file number.
* PR #396 from @Andrew-S-Rosen (#396)
    This PR overhauls (and greatly simplifies) the termination logic in the `VaspJob`. The major problem this PR seeks to solve is described in https://github.com/Matgenix/jobflow-remote/issues/323#issuecomment-3249870277 and can be summarized as follows.
    In some job orchestration setups, Custodian might end up running on a master node with the VASP processes being launched on sister nodes. This is often done, for instance, when requesting a single large Slurm allocation and running many concurrent VASP processes therein.  Currently, Custodian cannot handle this setup, as the Custodian process on the master node seemingly does not have permission to kill the VASP process on the other node(s) in the allocation, and it then defaults to a `killall` command killing everything (including perfectly fine jobs). However, Custodian does have permission to kill the parent process that launches the VASP executable (typically an `srun` or `mpirun` call), which in fact is what the `killall` indiscriminately kills.
    This PR resolves the issue and fixes the somewhat hacky logic that was in place before.
* PR #399 from @Andrew-S-Rosen (#399)
    The `grad_not_orth` handler previously did nothing if a Meta-GGA or hybrid functional was used. Now, it switches ALGO to Normal.
* PR #402 from @Andrew-S-Rosen (#402)
    Closes #392. This is a non-fixable error, so we just warn the user to fix their INCAR. We don't make the change for them because it was probably a conceptual error.
* PR #395 from @Andrew-S-Rosen (#395)
    Closes #394. As noted in the [VASP manual](https://www.vasp.at/wiki/index.php/ISEARCH), it is strongly recommended to use ISEARCH = 1 (default: ISEARCH = 0) when setting ALGO = All. Currently, Custodian does not do this but should. This PR adds ISEARCH = 1 alongside ALGO = All actions.
    There are two subtleties to keep in mind:
* PR #391 from @Andrew-S-Rosen (#391)
    Previously, the `nbands_not_sufficient` error in VASP was treated as unfixable. Now, the handler will automatically increase `NBANDS` to the default value within VASP.
* PR #388 from @Andrew-S-Rosen (#388)
    Closes #387. With the reliance on absolute rather than relative file paths in https://github.com/materialsproject/custodian/pull/317, the use of the `scratch_dir` keyword argument seems to have been broken, as jobs were always run in the current working directory rather than the scratch directory.
* PR #386 from @esoteric-ephemera (#386)
    - QCHEM: ensure variables are correctly initialized given their expected type (issues with mixed `dict` / `None` init)
    - VASP: ensure `eddrm` handler terminates a calculation once POTIM has reached the defined threshhold (0.01)
* PR #381 from @Andrew-S-Rosen (#381)
    Closes #380.
    **Fixes:**
    - The `error.tar.gz` files now unpack without including the full file path of the original files that were tar'd.
* PR #355 from @naik-aakash (#355)
    Hi @JaGeo  and @shyuep, I have updated the list of output files from LOBSTER here. These are optional files that can be generated using lobster >=v5.
* PR #361 from @yanghan234 (#361)
    - In finite field calculations, the OUTCAR prints the calculations for all of the requested directions. Updated the codes to parse electronic iterations.
* PR #375 from @Andrew-S-Rosen (#375)
    Closes #374.
    This PR makes a change to the logic for choosing whether a VASP calculation should be run with the gamma-point only version of VASP (typically `vasp_gam`) or not. Specifically, we no longer check for whether the KPOINTS file is gamma-centered or not. This is because a 1x1x1 Monkhorst-Pack grid should be the same as a 1x1x1 Gamma-centered grid. An analogous change was made for the KSPACING-related check.
* PR #358 from @janosh (#358)
    also use `logger.exception` instead of `logger.warning` in `VaspJob.terminate` to get full stacktrace which can help a lot with debugging
    I discussed `AMIX` effectiveness with @Andrew-S-Rosen prior to this PR. also pinging @esoteric-ephemera in case you want to chime in
* PR #373 from @esoteric-ephemera (#373)
    Adds support for correcting two VASP errors:
    - [FEXCF](https://www.vasp.at/forum/viewtopic.php?p=14827), close #365
    - [IBZKPT](https://www.vasp.at/forum/viewtopic.php?p=24485)
    Also ensure that $\Gamma$-point only VASP isn't run when DFPT calcs are run (either / both `LEPSILON` or `LOPTICS` are True)
    To do:
    - Add tests* PR #362 from @Andrew-S-Rosen (#362)
    Anytime that we modify NCORE, we should also unset NPAR if it's present in the INCAR file since NPAR takes precedence. This is done throughout Custodian, but there was one spot missing it. I added it in.
* PR #356 from @esoteric-ephemera (#356)
    Two major changes:
    - Since `LargeSigmaHandler` is a monitor handler (checks while output is still being written), it can occasionally misfire when parsing data from OUTCAR. This adds a fix to prevent jobs from being terminated when the handler itself fails to interpret partial file output
    - Close [#348](https://github.com/materialsproject/custodian/issues/348) by expanding the scope of k-point checks to include KSPACING, and to also check for grid shifts in KPOINTS
* PR #349 from @soge8904 (#349)
    This PR is to add jobs.py for JDFTx. We have a draft PR open on atomate2 to integrate JDFTx, but it seems that this script belongs here. Jobs.py was created using the CP2K template, with only the basic functionalities for now (just enough to run a job).
* PR #342 from @esoteric-ephemera (#342)
    Minor update to the logic of the `auto_nbands` check for `VaspErrorHandler`. This check sees if the number of bands has been updated by VASP, and currently it only checks to see if that updated number is very large.
    However, there are cases where the user specifies an NBANDS that is incompatible with their parallelization settings, as NBANDS must be divisible by $(\mathrm{ranks}) / (\mathrm{KPAR} \times \mathrm{NCORE})$. In these cases, VASP increases the number of bands to ensure the calculation can still proceed. This can happen in MP's band structure workflows with uniform $k$-point densities.
    However, since the current `auto_nbands` handler applies no corrections to the job, these otherwise successful runs are killed.
    This PR adds logic to ensure that the calculation is rerun with a higher number of bands appropriate to the parallelization setting. This is kinda redundant, since VASP already does this. But I think it has to occur this way because `VaspErrorHandler` is monitoring the job and flags it for an `auto_nbands` error.
    Another implementation concern: it's generally safer to decrease the number of bands since this requires a lower energy cutoff to converge each band. It might be safer to decrease NBANDS as a fix
* PR #341 from @zulissimeta (#341)
    Address #340 . Problem: the base Modder() class also sets the directory, so the call to the super `__init__` also needs the directory.

## 2025.8.13
* PR #388 from @Andrew-S-Rosen (#388)
    Closes #387. With the reliance on absolute rather than relative file paths in https://github.com/materialsproject/custodian/pull/317, the use of the `scratch_dir` keyword argument seems to have been broken, as jobs were always run in the current working directory rather than the scratch directory.
    This PR fixes the `scratch_dir` keyword argument by ensuring that the jobs are properly run in the created scratch directory.
    This PR also fixes an issue with `gzipped_output` not being thread-safe due to a stray relative path.
* PR #386 from @esoteric-ephemera (#386)
    - QCHEM: ensure variables are correctly initialized given their expected type (issues with mixed `dict` / `None` init)
    - VASP: ensure `eddrm` handler terminates a calculation once POTIM has reached the defined threshhold (0.01)
* PR #381 from @Andrew-S-Rosen (#381)
    Closes #380.
    **Fixes:**
    - The `error.tar.gz` files now unpack without including the full file path of the original files that were tar'd.
    **Changes**:
    - I have made it so that doing `tar -xvf error1.tar.gz` will not accidentally overwrite files in the parent directory. The files will be written out to `error.1/*` instead.
    **Maintenance**:
    - I added a few missing tests and a regression test for #380.
* PR #355 from @naik-aakash (#355)
    Hi @JaGeo  and @shyuep, I have updated the list of output files from LOBSTER here. These are optional files that can be generated using lobster >=v5.
    This should also get gzipped now if a user runs with keywords that enable such calculations.
    # Todo
    - [x] Add test files and update tests
* PR #361 from @yanghan234 (#361)
    This PR solves #360
    Major changes:
    - In finite field calculations, the OUTCAR prints the calculations for all of the requested directions. Updated the codes to parse electronic iterations.
* PR #375 from @Andrew-S-Rosen (#375)
    Closes #374.
    This PR makes a change to the logic for choosing whether a VASP calculation should be run with the gamma-point only version of VASP (typically `vasp_gam`) or not. Specifically, we no longer check for whether the KPOINTS file is gamma-centered or not. This is because a 1x1x1 Monkhorst-Pack grid should be the same as a 1x1x1 Gamma-centered grid. An analogous change was made for the KSPACING-related check.
    The tests have been updated, and two previously missing tests have been added:
    - A test to make sure the standard version of VASP is used when the kpoints are not 1x1x1
    - A test to make sure that the standard version of VASP is used when a small KSPACING is set
* PR #373 from @esoteric-ephemera (#373)
    Adds support for correcting two VASP errors:
    - [FEXCF](https://www.vasp.at/forum/viewtopic.php?p=14827), close #365
    - [IBZKPT](https://www.vasp.at/forum/viewtopic.php?p=24485)
    Also ensure that $\Gamma$-point only VASP isn't run when DFPT calcs are run (either / both `LEPSILON` or `LOPTICS` are True)
    To do:
    - Add tests
* PR #362 from @Andrew-S-Rosen (#362)
    Anytime that we modify NCORE, we should also unset NPAR if it's present in the INCAR file since NPAR takes precedence. This is done throughout Custodian, but there was one spot missing it. I added it in.
* PR #356 from @esoteric-ephemera (#356)
    Two major changes:
    - Since `LargeSigmaHandler` is a monitor handler (checks while output is still being written), it can occasionally misfire when parsing data from OUTCAR. This adds a fix to prevent jobs from being terminated when the handler itself fails to interpret partial file output
    - Close [#348](https://github.com/materialsproject/custodian/issues/348) by expanding the scope of k-point checks to include KSPACING, and to also check for grid shifts in KPOINTS
* PR #349 from @soge8904 (#349)
    Hi,
    This PR is to add jobs.py for JDFTx. We have a draft PR open on atomate2 to integrate JDFTx, but it seems that this script belongs here. Jobs.py was created using the CP2K template, with only the basic functionalities for now (just enough to run a job).
    ## Todos
    If this is work in progress, what else needs to be done?
    - feature 2: ...
    - fix 2:
* PR #342 from @esoteric-ephemera (#342)
    Minor update to the logic of the `auto_nbands` check for `VaspErrorHandler`. This check sees if the number of bands has been updated by VASP, and currently it only checks to see if that updated number is very large.
    However, there are cases where the user specifies an NBANDS that is incompatible with their parallelization settings, as NBANDS must be divisible by $(\mathrm{ranks}) / (\mathrm{KPAR} \times \mathrm{NCORE})$. In these cases, VASP increases the number of bands to ensure the calculation can still proceed. This can happen in MP's band structure workflows with uniform $k$-point densities.
    However, since the current `auto_nbands` handler applies no corrections to the job, these otherwise successful runs are killed.
    This PR adds logic to ensure that the calculation is rerun with a higher number of bands appropriate to the parallelization setting. This is kinda redundant, since VASP already does this. But I think it has to occur this way because `VaspErrorHandler` is monitoring the job and flags it for an `auto_nbands` error.
    Another implementation concern: it's generally safer to decrease the number of bands since this requires a lower energy cutoff to converge each band. It might be safer to decrease NBANDS as a fix
* PR #341 from @zulissimeta (#341)
    Address #340 . Problem: the base Modder() class also sets the directory, so the call to the super `__init__` also needs the directory.
    ## Todos
    Could do with some unit tests! Nothing new added though.

## 2025.5.12
* PR #355 from @naik-aakash (#355) updated the list of output files from LOBSTER
* PR #361 from @yanghan234 (#361)
    - In finite field calculations, the OUTCAR prints the calculations for all of the requested directions. Updated the codes to parse electronic iterations.
* PR #375 from @Andrew-S-Rosen (#375)
    Closes #374.
    This PR makes a change to the logic for choosing whether a VASP calculation should be run with the gamma-point only version of VASP (typically `vasp_gam`) or not. Specifically, we no longer check for whether the KPOINTS file is gamma-centered or not. This is because a 1x1x1 Monkhorst-Pack grid should be the same as a 1x1x1 Gamma-centered grid. An analogous change was made for the KSPACING-related check.
    The tests have been updated, and two previously missing tests have been added:
    - A test to make sure the standard version of VASP is used when the kpoints are not 1x1x1
    - A test to make sure that the standard version of VASP is used when a small KSPACING is set
* PR #373 from @esoteric-ephemera (#373)
    Adds support for correcting two VASP errors:
    - [FEXCF](https://www.vasp.at/forum/viewtopic.php?p=14827), close #365
    - [IBZKPT](https://www.vasp.at/forum/viewtopic.php?p=24485)
    Also ensure that $\Gamma$-point only VASP isn't run when DFPT calcs are run (either / both `LEPSILON` or `LOPTICS` are True)

## 2025.4.14
* SYMPREC is now properly rounded when they are modified by custodian.
* PR #362 from @Andrew-S-Rosen (#362)
    Anytime that we modify NCORE, we should also unset NPAR if it's present in the INCAR file since NPAR takes precedence. This is done throughout Custodian, but there was one spot missing it. I added it in.
* PR #356 from @esoteric-ephemera (#356)
    Two major changes:
    - Since `LargeSigmaHandler` is a monitor handler (checks while output is still being written), it can occasionally misfire when parsing data from OUTCAR. This adds a fix to prevent jobs from being terminated when the handler itself fails to interpret partial file output
    - Close [#348](https://github.com/materialsproject/custodian/issues/348) by expanding the scope of k-point checks to include KSPACING, and to also check for grid shifts in KPOINTS
* PR #349 from @soge8904 (#349)
    Hi,
    This PR is to add jobs.py for JDFTx. We have a draft PR open on atomate2 to integrate JDFTx, but it seems that this script belongs here. Jobs.py was created using the CP2K template, with only the basic functionalities for now (just enough to run a job).
* PR #346 from @Andrew-S-Rosen (#346)
    As recommended in [pep 0561](https://peps.python.org/pep-0561/), a blank `py.typed` marker should be included when type hints are used so downstream codes can type check with `mypy` and similar tools. There aren't many type hints in this code, but there are some.
    I also removed the reliance on `numpy==1.26.4` in the test suite since this caused other issues due to https://github.com/materialsproject/pymatgen/issues/3990.
* PR #342 from @esoteric-ephemera (#342)
    Minor update to the logic of the `auto_nbands` check for `VaspErrorHandler`. This check sees if the number of bands has been updated by VASP, and currently it only checks to see if that updated number is very large.
    However, there are cases where the user specifies an NBANDS that is incompatible with their parallelization settings, as NBANDS must be divisible by $(\mathrm{ranks}) / (\mathrm{KPAR} \times \mathrm{NCORE})$. In these cases, VASP increases the number of bands to ensure the calculation can still proceed. This can happen in MP's band structure workflows with uniform $k$-point densities.
    However, since the current `auto_nbands` handler applies no corrections to the job, these otherwise successful runs are killed.
    This PR adds logic to ensure that the calculation is rerun with a higher number of bands appropriate to the parallelization setting. This is kinda redundant, since VASP already does this. But I think it has to occur this way because `VaspErrorHandler` is monitoring the job and flags it for an `auto_nbands` error.
    Another implementation concern: it's generally safer to decrease the number of bands since this requires a lower energy cutoff to converge each band. It might be safer to decrease NBANDS as a fix
* PR #341 from @zulissimeta (#341)
    Address #340 . Problem: the base Modder() class also sets the directory, so the call to the super `__init__` also needs the directory.

## 2024.10.16
* Add a update_incar option in VaspJob which updates parameters from a previous vasprun.xml.

## 2024.10.15
* Bug fix for pip installation.

## 2024.10.14
* PR #342 from @esoteric-ephemera (#342)
    Minor update to the logic of the `auto_nbands` check for `VaspErrorHandler`. This check sees if the number of bands has been updated by VASP, and currently it only checks to see if that updated number is very large.
    However, there are cases where the user specifies an NBANDS that is incompatible with their parallelization settings, as NBANDS must be divisible by $(\mathrm{ranks}) / (\mathrm{KPAR} \times \mathrm{NCORE})$. In these cases, VASP increases the number of bands to ensure the calculation can still proceed. This can happen in MP's band structure workflows with uniform $k$-point densities.
    However, since the current `auto_nbands` handler applies no corrections to the job, these otherwise successful runs are killed.
    This PR adds logic to ensure that the calculation is rerun with a higher number of bands appropriate to the parallelization setting. This is kinda redundant, since VASP already does this. But I think it has to occur this way because `VaspErrorHandler` is monitoring the job and flags it for an `auto_nbands` error.
    Another implementation concern: it's generally safer to decrease the number of bands since this requires a lower energy cutoff to converge each band. It might be safer to decrease NBANDS as a fix

## 2024.6.24
- Improved handling of ISMEAR for NKPT<4 (@Andrew-S-Rosen, @esoteric-ephemera)

## 2024.4.18
- Enable export of environment variables plus lobster run as a command enhancement lobster (@JaGeo)
- New Gaussian plugin (@rashatwi)
- Add missing directory kwarg on QCJob run() method (@Andrew-S-Rosen)
- Add support for directory for Q-Chem (@Andrew-S-Rosen)

## 2024.3.12

* Make Custodian threadsafe with explicit file paths (@zulissimeta).

## v2024.2.15

### 🐛 Bug Fixes

* Fix `KspacingMetalHandler` triggering on runs that don't use `KSPACING` by @janosh in https://github.com/materialsproject/custodian/pull/298
* Fixed a small issue with the erroneous attribute call on a Structure object in AMIN handler by @fyalcin in https://github.com/materialsproject/custodian/pull/297
* Move `TEST_DIR` + `TEST_FILES` from `custodian/__init__.py` to `tests/conftest.py` by @janosh in https://github.com/materialsproject/custodian/pull/312

### 🛠 Enhancements

* Rewrite handler tests by @janosh in https://github.com/materialsproject/custodian/pull/299
* Fix `AliasingErrorHandlerTest` modifying test files by @janosh in https://github.com/materialsproject/custodian/pull/301
* Caching parsed output files by @gpetretto in https://github.com/materialsproject/custodian/pull/273

### 🧹 House-Keeping

* Move tests to their own root-level directory by @janosh in https://github.com/materialsproject/custodian/pull/305
* Refactor test file copying by @janosh in https://github.com/materialsproject/custodian/pull/306
* Move `_clear_tracked_cache` fixture by @gpetretto in https://github.com/materialsproject/custodian/pull/307
* Don't needlessly inherit from `unittest.TestCase` by @janosh in https://github.com/materialsproject/custodian/pull/308

### 🧪 Tests

* Add new error handlers, add tests for NonConvergingErrorHandler by @esoteric-ephemera in https://github.com/materialsproject/custodian/pull/313

### 🏥 Package Health

* Merge `setup.py` into `pyproject.toml` by @janosh in https://github.com/materialsproject/custodian/pull/304
* Fix release CI by @janosh in https://github.com/materialsproject/custodian/pull/314

### 🤷‍♂️ Other Changes

* Add eddiag error handling and fix AMIN error handling in VaspErrorHandler by @esoteric-ephemera in https://github.com/materialsproject/custodian/pull/302

## New Contributors

* @esoteric-ephemera made their first contribution in https://github.com/materialsproject/custodian/pull/302

**Full Changelog**: https://github.com/materialsproject/custodian/compare/v2023.10.9...v2024.2.15

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

* Fix for LargeSigmaHandler. Now defaults to ISMEAR=1 and fallback to ISMEAR=0 if SIGMA has been modified
  three times from 0.2 (@Andrew-S-Rosen, @janosh)
* More robust VASP job termination (@fyalcin)

## v2023.6.5

* New VASP error handler for invalid INCAR parameter (@Andrew-S-Rosen)
* Change VASP terminate function to be sensitive to execution directory (@MichaelWolloch)
* Add handler for invalid WAVECAR when going from vasp_gam to vasp_std (@Andrew-S-Rosen)

## v2023.5.12

* Add back kwargs to VaspHandler to maintain backward compatibility (@Andrew-S-Rosen)

## v2023.5.7

* VASP Handler: Better error checking for too_few_nbands (@Andrew-S-Rosen)
* VASP Handler: General clean up and mitigating unnecessary INCAR swaps (@Andrew-S-Rosen)
* VASP Handler: Remove deprecated handlers and kwargs (@Andrew-S-Rosen)
* VASP Handler: Add a new correction for the ZPOTRF ZTRTRI error that is specific to small structures (@Andrew-S-Rosen)
* VASP Handler: Add a new handler for the SET_CORE_WF error (@Andrew-S-Rosen)
* VASP Handler: Only apply the algo_tet handler if SCF convergence failed (@Andrew-S-Rosen)
* VASP Handler: AMIN handler should only be applied if SCF is not converged (@Andrew-S-Rosen)
* VASP Handler: Do not set ADDGRID to True (@Andrew-S-Rosen)

## v2023.3.8

* Updates for QChem6 support (@samblau)
* Updates for CP2K support (@nwinner)

## v2022.5.26

* PR #219 from @samblau. Q-Chem updates to NBO, new geometry optimizer, revamped SCF error handling.

## v2022.5.17

* PR #220 from @yury-lysogorskiy. Fix for NBANDS when NBANDS is very small.
* PR #211 from @Andrew-S-Rosen. Handler for error in reading plane wave coeff.
* PR #214 from @Andrew-S-Rosen. Handler for `ZHEGV` error by reducing number of cores.
* PR #215 from @Andrew-S-Rosen. Fix for new `ZPOTRF` error phrasing.
* PR #210 from @nwinner. CP2K support.

## v2022.2.13

* Support for new Lobster versions (@naik-aakash)
* Bug fix for termination of gamma VASP runs.

## v2022.1.17

* New NBANDS not sufficient handler in VASP (@Andrew-S-Rosen)
* New VASP error handling for VASP 6.2.1 HNFORM error (@Andrew-S-Rosen)
* Improve zbrent handler by trying to get IBRION = 2 to succeed before switching to IBRION = 1 (@Andrew-S-Rosen)
* Updates to ALGO handling with grad_not_orth and algo_tet (@Andrew-S-Rosen)

## v2021.12.2

* Address new VASP6 inconsistent Bravais lattice error (@Andrew-S-Rosen)
* Don't check for drift if NSW = 1 (@Andrew-S-Rosen)
* [VASP] Switch from IBRION = 1 --> 2 if the BRIONS error occurs more than once (@Andrew-S-Rosen)
* Handle finite difference ncore error (@utf)
* [VASP] More robust zbrent fix (@Andrew-S-Rosen)
* [VASP] Increase posmap error count (@Andrew-S-Rosen)
* [VASP] Update real_optlay logic to avoid LREAL = True (@Andrew-S-Rosen)
* [VASP] More appropriate grad_not_orth fix and new algo_tet error handler (@Andrew-S-Rosen)
* [VASP] Adjust SCF Ladder for meta-GGAs/hybrids (@Andrew-S-Rosen)
* Refactor VaspErrorHandler.check() (@janosh)
* Fix VaspErrorHandler not handling "tetrahedron method fails" (@janosh)

## v2021.2.8

* Allow static calculations with ISMEAR = -5 for metals (@MichaelWolloch).

## v2021.1.8

* New handlers for VASP6 (@mkhorton, @rkingsbury)

## v2021.1.7

* Improved handling of scratch directories and update for QChem.

## v2019.8.24

* Cleanup codestyle, which is now enforced.
* Py3k support only, in line with pymatgen.
* Update dependencies.
* Sentry support (@mkhorton).
* Complete qchem overhaul (frequency flattening optimization, refined error
  handlers) (@samblau)

## v2019.2.10

* Improved slow convergence handling. (@shyamd)

## v2019.2.7

* Improved error logging.
* Improved handling of frozen jobs and potim errors.
* Improved Exceptino handling. (Guido Petretto)

## v2017.12.23

* cstdn command line tool is now official with docs.
* Fine-grained control of VaspErrorHandler is now possible using
  `errors_subset_to_catch`.
* Switched to date-based versioning for custodian like pymatgen.

## v1.1.1

* DriftErrorHandler (Shyam)

## v1.1.0

* Improved error handling for Qchem calculations.

## v1.0.4

* Improved handling of non-zero return codes.

## v1.0.2

* Interrupted run feature. (Shyam Dwaraknath)

## v1.0.1

* Pymatgen 4.0.0 compatible release.

## v1.0.0

* Custodian now comes with a "cstdn" script that enables the arbitrary creation
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
.org/pypi/monty>`\_, which is now a dependency
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
   to specify the jobs to be performed in scratch. Especially useful for
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

1. Added handling of PRICEL error in VASP.
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
