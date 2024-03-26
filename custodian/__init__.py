"""
Custodian is a simple, robust and flexible just-in-time (JIT) job management
framework written in Python.
"""

import os

from .custodian import Custodian

__author__ = (
    "Shyue Ping Ong, William Davidson Richards, Stephen Dacek, Xiaohui Qu, Matthew Horton, "
    "Samuel M. Blau, Janosh Riebesell"
)
__version__ = "2024.3.12"


PKG_DIR = os.path.dirname(__file__)
ROOT = os.path.dirname(PKG_DIR)
