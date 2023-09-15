---
layout: default
title: custodian.feff.handlers.md
nav_exclude: true
---

# custodian.feff.handlers module

This module implements specific error handler for FEFF runs.


### _class_ custodian.feff.handlers.UnconvergedErrorHandler(output_filename='log1.dat')
Bases: [`ErrorHandler`](custodian.custodian.md#custodian.custodian.ErrorHandler)

Correct the unconverged error of FEFF’s SCF calculation.

Initializes the handler with the output file to check


* **Parameters**

    **output_filename** (*str*) – Filename for the log1.dat file. log1.dat file
    contains the SCF calculation convergence information. Change this only
    if it is different from the default (unlikely).



#### check()
If the FEFF run does not converge, the check will return
“TRUE”


#### correct()
Perform the corrections.


#### is_monitor(_ = Fals_ )
This class property indicates whether the error handler is a monitor,
i.e., a handler that monitors a job as it is running. If a
monitor-type handler notices an error, the job will be sent a
termination signal, the error is then corrected,
and then the job is restarted. This is useful for catching errors
that occur early in the run but do not cause immediate failure.