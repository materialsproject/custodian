"""
Custodian is a simple, robust and flexible just-in-time (JIT) job management
framework written in Python.
"""

import os
from importlib.metadata import PackageNotFoundError, version

from .custodian import Custodian

__author__ = (
    "Shyue Ping Ong, William Davidson Richards, Stephen Dacek, Xiaohui Qu, Matthew Horton, "
    "Samuel M. Blau, Janosh Riebesell, Andrew S. Rosen"
)
try:
    __version__ = version("custodian")
except PackageNotFoundError:  # pragma: no cover
    # package is not installed
    pass


PKG_DIR = os.path.dirname(__file__)
ROOT = os.path.dirname(PKG_DIR)
