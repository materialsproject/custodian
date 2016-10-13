# coding: utf-8

from __future__ import unicode_literals, division

"""
Utility function and classes.
"""


__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__date__ = "1/12/14"

from glob import glob
import logging
import os
import tarfile


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
    num = max([0] + [int(f.split(".")[1])
                     for f in glob("{}.*.tar.gz".format(prefix))])
    filename = "{}.{}.tar.gz".format(prefix, num + 1)
    logging.info("Backing up run to {}.".format(filename))
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
    host = os.environ.get('HOSTNAME', None)
    cluster = os.environ.get('SGE_O_HOST', None)
    if host is None:
        try:
            import socket
            host = host or socket.gethostname()
        except:
            pass
    return host or 'unknown', cluster or 'unknown'
