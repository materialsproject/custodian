---
layout: default
title: custodian.jdftx.jobs.md
nav_exclude: true
---

# custodian.jdftx.jobs module

This module implements basic kinds of jobs for JDFTx runs.

### *class* custodian.jdftx.jobs.JDFTxJob(jdftx_cmd, input_file='init.in', output_file='jdftx.out', stderr_file='std_err.txt')

Bases: `Job`

A basic JDFTx job. Runs whatever is in the working directory.

* **Parameters:**
  * **jdftx_cmd** (*str*) – Command to run JDFTx as a string.
  * **input_file** (*str*) – Name of the file to use as input to JDFTx
    executable. Defaults to “init.in”
  * **output_file** (*str*) – Name of file to direct standard out to.
    Defaults to “jdftx.out”.
  * **stderr_file** (*str*) – Name of file to direct standard error to.
    Defaults to “std_err.txt”.

#### postprocess(directory='./') → None

No post-processing required.

#### run(directory='./')

Perform the actual JDFTx run.

## Returns:

> (subprocess.Popen) Used for monitoring.

#### setup(directory='./') → None

No setup required.

#### terminate(directory='./') → None

Terminate JDFTx.

#### *static* terminate_process(proc, timeout=5)

Terminate a process gracefully, then forcefully if necessary.