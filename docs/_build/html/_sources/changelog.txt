Change Log
==========

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
