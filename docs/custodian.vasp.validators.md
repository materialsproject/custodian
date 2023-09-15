---
layout: default
title: custodian.vasp.validators.md
nav_exclude: true
---

# custodian.vasp.validators module

Implements various validatiors, e.g., check if vasprun.xml is valid, for VASP.


### _class_ custodian.vasp.validators.VaspAECCARValidator()
Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Check if the data in the AECCAR is corrupted

Dummy init


#### check()
Check for error.


### _class_ custodian.vasp.validators.VaspFilesValidator()
Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Check for existence of some of the files that VASP

    normally create upon running.

Dummy init


#### check()
Check for error.


### _class_ custodian.vasp.validators.VaspNpTMDValidator()
Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Check NpT-AIMD settings is loaded by VASP compiled with -Dtbdyn.
Currently, VASP only have Langevin thermostat (MDALGO = 3) for NpT ensemble.

Dummy init.


#### check()
Check for error.


### _class_ custodian.vasp.validators.VasprunXMLValidator(output_file='vasp.out', stderr_file='std_err.txt')
Bases: [`Validator`](custodian.custodian.md#custodian.custodian.Validator)

Checks that a valid vasprun.xml was generated


* **Parameters**


    * **output_file** (*str*) – Name of file VASP standard output is directed to.
    Defaults to “vasp.out”.


    * **stderr_file** (*str*) – Name of file VASP standard error is direct to.
    Defaults to “std_err.txt”.



#### check()
Check for error.


### custodian.vasp.validators.check_broken_chgcar(chgcar, diff_thresh=None)
Check if the charge density file is corrupt
:param chgcar: Chgcar-like object.
:type chgcar: Chgcar
:param diff_thresh: Threshold for diagonal difference.

> None means we won’t check for this.