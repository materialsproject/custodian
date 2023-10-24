---
layout: default
title: custodian.utils.md
nav_exclude: true
---

# custodian.utils module

Utility function and classes.

## custodian.utils.backup(filenames, prefix=’error’)

Backup files to a tar.gz file. Used, for example, in backing up the
files of an errored run before performing corrections.

* **Parameters**
  * **filenames** (*[**str**]*) – List of files to backup. Supports wildcards, e.g.,
    *.*.
  * **prefix** (*str*) – prefix to the files. Defaults to error, which means a
    series of error.1.tar.gz, error.2.tar.gz, … will be generated.

## custodian.utils.get_execution_host_info()

Tries to return a tuple describing the execution host.
Doesn’t work for all queueing systems

* **Returns**

  (HOSTNAME, CLUSTER_NAME)