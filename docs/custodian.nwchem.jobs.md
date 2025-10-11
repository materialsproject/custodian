---
layout: default
title: custodian.nwchem.jobs.md
nav_exclude: true
---

# custodian.nwchem.jobs module

This module implements basic kinds of jobs for Nwchem runs.

## *class* custodian.nwchem.jobs.NwchemJob(nwchem_cmd, input_file=’mol.nw’, output_file=’mol.nwout’, gzipped=False, backup=True, settings_override=None)

Bases: [`Job`](custodian.custodian.md#custodian.custodian.Job)

A basic Nwchem job.

Initializes a basic NwChem job.

* **Parameters**
  * **nwchem_cmd** (    *[**str**]*) – Command to run Nwchem as a list of args. For
    example, [“nwchem”].
  * **input_file** (*str*) – Input file to run. Defaults to “mol.nw”.
  * **output_file** (*str*) – Name of file to direct standard out to.
    Defaults to “mol.nwout”.
  * **backup** (*bool*) – Whether to backup the initial input files. If True,
    the input files will be copied with a “.orig” appended.
    Defaults to True.
  * **gzipped** (*bool*) – Deprecated. Please use the Custodian class’s
    gzipped_output option instead.
  * **settings_override** (    *[**dict**]*) – An ansible style list of dict to override changes.
    #TODO: Not implemented yet.

### postprocess()

Renaming or gzipping as needed.

### run()

Performs actual nwchem run.

### setup()

Performs backup if necessary.