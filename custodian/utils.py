#!/usr/bin/env python

"""
Utility function and classes.
"""

from __future__ import division

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "shyuep@gmail.com"
__date__ = "1/12/14"

import os
from glob import glob
import logging
import shutil
import tempfile
import tarfile
from gzip import GzipFile


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


def gzip_dir(path):
    """
    Gzips all files in a directory. Used, for instance, to compress all
    files at the end of a run.

    Args:
        path (str): Path to directory.
    """
    for f in os.listdir(path):
        if not f.endswith("gz"):
            with open(f, 'rb') as f_in, \
                    GzipFile('{}.gz'.format(f), 'wb') as f_out:
                f_out.writelines(f_in)
            os.remove(f)


def recursive_copy(src, dst):
    """
    Implements a recursive copy function similar to Unix's "cp -r" command.
    Surprisingly, python does not have a real equivalent. shutil.copytree
    only works if the destination directory is not present.

    Args:
        src (str): Source folder to copy.
        dst (str): Destination folder.
    """
    for parent, subdir, files in os.walk(src):
        parent = os.path.relpath(parent)
        realdst = dst if parent == "." else os.path.join(dst, parent)
        try:
            os.makedirs(realdst)
        except Exception as ex:
            pass
        for f in files:
            shutil.copy(os.path.join(parent, f), realdst)


class ScratchDir(object):
    """
    Creates a with context manager that automatically handles creation of
    temporary directories in the scratch space and cleanup when done.
    """

    SCR_LINK = "scratch_link"

    def __init__(self, rootpath):
        """
        Initializes scratch directory given a **root** path. There is no need
        to try to create unique directory names. The code will generate a
        temporary sub directory in the rootpath. The way to use this is using a
        with context manager. Example::

            with ScratchDir("/scratch"):
                do_something()

        Args:
            rootpath (str):
                The path in which to create temp subdirectories.
        """
        self.rootpath = rootpath
        self.cwd = os.getcwd()

    def __enter__(self):
        tempdir = self.cwd
        if self.rootpath is not None and os.path.abspath(self.rootpath) != \
                self.cwd:
            tempdir = tempfile.mkdtemp(dir=self.rootpath)
            self.tempdir = os.path.abspath(tempdir)
            recursive_copy(".", tempdir)
            os.symlink(tempdir, ScratchDir.SCR_LINK)
            os.chdir(tempdir)
            logging.info(
                "Using scratch directory {} and created symbolic "
                "link called {} in working directory".format(
                    tempdir, ScratchDir.SCR_LINK))
        return tempdir

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.rootpath is not None and os.path.abspath(self.rootpath) != \
                self.cwd:
            recursive_copy(".", self.cwd)
            shutil.rmtree(self.tempdir)
            os.chdir(self.cwd)
            os.remove(ScratchDir.SCR_LINK)