---
layout: default
title: custodian.feff.jobs.md
nav_exclude: true
---

# custodian.feff.jobs module

This module implements basic kinds of jobs for FEFF runs.

## *class* custodian.feff.jobs.FeffJob(feff_cmd, output_file=’feff.out’, stderr_file=’std_feff_err.txt’, backup=True, gzipped=False, gzipped_prefix=’feff_out’)

Bases: [`Job`](custodian.custodian.md#custodian.custodian.Job)

A basic FEFF job, run whatever is in the directory.

This constructor is used for a standard FEFF initialization

* **Parameters**
  * **feff_cmd** (*str*) – the name of the full executable for running FEFF
  * **output_file** (*str*) – Name of file to direct standard out to.
    Defaults to “feff.out”.
  * **stderr_file** (*str*) – Name of file direct standard error to.
    Defaults to “std_feff_err.txt”.
  * **backup** (*bool*) – Indicating whether to backup the initial input files.
    If True, the feff.inp will be copied with a “.orig” appended.
    Defaults to True.
  * **gzipped** (*bool*) – Whether to gzip the final output. Defaults to False.
  * **gzipped_prefix** (*str*) – prefix to the feff output files archive. Defaults
    to feff_out, which means a series of feff_out.1.tar.gz, feff_out.2.tar.gz, …
    will be generated.

### postprocess()

Renaming or gzipping all the output as needed

### run()

Performs the actual FEFF run
:returns: (subprocess.Popen) Used for monitoring.

### setup()

Performs initial setup for FeffJob, do backing up.
Returns: