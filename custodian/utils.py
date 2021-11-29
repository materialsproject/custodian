"""
Utility function and classes.
"""

import logging
import os
import tarfile
from glob import glob


def backup(filenames, prefix="error"):
    """
    Backup files to a tar.gz file. Used, for example, in backing up the
    files of an errored run before performing corrections.

    Args:
        filenames ([str]): List of files to backup. Supports wildcards, e.g.,
            *.*.
        prefix (str): prefix to the files. Defaults to error, which means a
            series of error.1.tar.gz, error.2.tar.gz, ... will be generated.
    """
    num = max([0] + [int(f.split(".")[1]) for f in glob(f"{prefix}.*.tar.gz")])
    filename = f"{prefix}.{num + 1}.tar.gz"
    logging.info(f"Backing up run to {filename}.")
    with tarfile.open(filename, "w:gz") as tar:
        for fname in filenames:
            for f in glob(fname):
                tar.add(f)


def get_execution_host_info():
    """
    Tries to return a tuple describing the execution host.
    Doesn't work for all queueing systems

    Returns:
        (HOSTNAME, CLUSTER_NAME)
    """
    host = os.environ.get("HOSTNAME", None)
    cluster = os.environ.get("SGE_O_HOST", None)
    if host is None:
        try:
            import socket

            host = host or socket.gethostname()
        except Exception:
            pass
    return host or "unknown", cluster or "unknown"
