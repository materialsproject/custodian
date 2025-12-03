"""Utility function and classes."""

import functools
import logging
import os
import tarfile
from glob import glob
from typing import ClassVar


def backup(filenames, prefix="error", directory="./") -> None:
    """
    Backup files to a tar.gz file. Used, for example, in backing up the
    files of an errored run before performing corrections.

    Args:
        filenames ([str]): List of files to backup. Supports wildcards, e.g.,
            *.*.
        prefix (str): prefix to the files. Defaults to error, which means a
            series of error.1.tar.gz, error.2.tar.gz, ... will be generated.
        directory (str): directory where the files exist
    """
    backup_files = glob(os.path.join(directory, f"{prefix}.*.tar*"))
    nums = [0]
    for file in backup_files:
        try:
            if file.endswith(".tar.gz"):
                nums.append(int(file.split(".")[-3]))
            elif file.endswith(".tar"):
                nums.append(int(file.split(".")[-2]))
        except (ValueError, IndexError):
            continue
    num = max(nums)
    prefix = f"{prefix}.{num + 1}"
    filename = os.path.join(directory, f"{prefix}.tar.gz")
    logging.info(f"Backing up run to {filename}")
    with tarfile.open(filename, "w:gz") as tar:
        for fname in filenames:
            for file in glob(os.path.join(directory, fname)):
                tar.add(file, arcname=os.path.join(prefix, os.path.basename(file)))


def get_execution_host_info():
    """
    Tries to return a tuple describing the execution host.
    Doesn't work for all queueing systems.

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


class tracked_lru_cache:
    """
    Decorator wrapping the functools.lru_cache adding a tracking of the
    functions that have been wrapped.

    Exposes a method to clear the cache of all the wrapped functions.

    Used to cache the parsed outputs in handlers/validators, to avoid
    multiple parsing of the same file.
    Allows Custodian to clear the cache after all the checks have been performed.
    """

    cached_functions: ClassVar[set] = set()

    def __init__(self, func) -> None:
        """
        Args:
            func: function to be decorated.
        """
        self.func = functools.lru_cache(func)
        functools.update_wrapper(self, func)

        # expose standard lru_cache functions
        self.cache_info = self.func.cache_info
        self.cache_clear = self.func.cache_clear

    def __call__(self, *args, **kwargs):
        """Call the decorated function."""
        result = self.func(*args, **kwargs)
        self.cached_functions.add(self.func)
        return result

    @classmethod
    def tracked_cache_clear(cls) -> None:
        """Clear the cache of all the decorated functions."""
        while cls.cached_functions:
            f = cls.cached_functions.pop()
            f.cache_clear()
