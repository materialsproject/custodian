Change Log
==========

0.6.3
-----
1. Added buffer time option in PBSWalltimeHandler.
2. Improved Qchem jobs and handlers (Xiaohui Qu).
3. Vastly improved API docs.

0.6.2
-----
1. Bug fix release to support sub dirs in run folder when using scratch.
2. Improve handling of walltime in PBSWalltimeHander.

0.6.1
-----
1. Bug fix release to address minor issue with checkpointing.
2. Checkpointing is now turned off by default.

0.6.0
-----
1. Checkpointing implemented for Custodian. Custodian can now checkpoint all
   files in the current working directory after every successful job. If the
   job is resubmitted, it will restore files and start from the last
   checkpoint. Particularly useful for multi-job runs.
2. Added PBSWalltimeHandler to handle wall times for PBS Vasp Jobs.
3. Qchem error handlers and jobs.

0.5.0
-----
1. Added scratch_dir option to Custodian class as well as run_vasp and
   run_nwchem scripts. Many supercomputing clusters have a scratch space
   which have significantly faster IO. This option provides a transparent way
   to specify the jobs to be performed in the scratch. Especially useful for
   jobs which have significant file IO.

0.4.5
-----
1. Fix gzip of output.

0.4.3
-----
1. Added handling for ZBRENT error for VASP.
2. Minor refactoring to consolidate backup and gzip directory methods.

0.4.2
-----
1. Rudimentary support for Nwchem error handling (by Shyue Ping Ong).
2. Improved VASP error handling (by Steve Dacek and Will Richards).

0.4.1
-----
1. Added hanlding of PRICEL error in VASP.
2. Speed and robustness improvements.
3. BRIONS error now handled by changing ISYM.

0.4.0
-----
1. Many VASP handlers are now consolidated into a single VaspErrorHandler.
2. Many more fixes for VASP runs, including the "TOO FEW BANDS",
   "TRIPLE PRODUCT", "DENTET" and "BRIONS" errors.
3. VaspJob now includes the auto_npar and auto_gamma options, which
   automatically optimizes the NPAR setting to be sqrt(number of cores) as
   per the VASP recommendation for DFT runs and tries to search for a
   gamma-only compiled version of VASP for gamma 1x1x1 runs.

0.3.5
-----
1. Bug fix for incorrect shift error handler in VASP.
2. More robust fix for unconverged VASP runs (switching from ALGO fast to
   normal).
3. Expanded documentation.

0.3.4
-----
1. Added support for handlers that perform monitor a job as it is progressing
   and terminates it if necessary. Useful for correcting errors that come up
   by do not cause immediate job failures.

0.3.2
-----
1. Important bug fix for VaspJob and converge_kpoints script.

0.3.0
-----

1. Major update to custodian API. Custodian now perform more comprehensive
   logging in a file called custodian.json, which logs all jobs and
   corrections performed.

Version 0.2.6
-------------
1. Bug fix for run_vasp script for static runs.

Version 0.2.5
-------------
1. run_vasp script that now provides flexible specification of vasp runs.
2. Vastly improved error handling for VASP runs.
3. Improved logging system for custodian.
4. Improved API for custodian return types during run.
5. First stable release.

Version 0.2.4
-------------

1. Bug fixes for aflow style runs assimilation.
