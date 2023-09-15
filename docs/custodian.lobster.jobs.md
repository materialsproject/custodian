---
layout: default
title: custodian.lobster.jobs.md
nav_exclude: true
---

# custodian.lobster.jobs module

This module implements jobs for Lobster runs.


### _class_ custodian.lobster.jobs.LobsterJob(lobster_cmd: str, output_file: str = 'lobsterout', stderr_file: str = 'std_err_lobster.txt', gzipped: bool = True, add_files_to_gzip=[], backup: bool = True)
Bases: [`Job`](custodian.custodian.md#custodian.custodian.Job)

Runs the Lobster Job


* **Parameters**


    * **lobster_cmd** – command to run lobster


    * **output_file** – usually lobsterout


    * **stderr_file** – standard output


    * **gzipped** – if True, Lobster files and add_files_to_gzip will be gzipped


    * **add_files_to_gzip** – list of files that should be gzipped


    * **backup** – if True, lobsterin will be copied to lobsterin.orig



#### postprocess()
will gzip relevant files (won’t gzip custodian.json and other output files from the cluster)


#### run()
runs the job


#### setup()
will backup lobster input files