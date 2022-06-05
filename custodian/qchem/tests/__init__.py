"""
Tests for QChem Custodian
"""

import os
import unittest

# skip QChem tests if openbabel is not installed but never skip them in CI
if "CI" not in os.environ:
    try:
        import openbabel
    except ImportError:
        raise unittest.SkipTest("Install openbabel to run the QChem tests in this directory.")
        # see .github/workflows/pytest.yml for install command

__author__ = "Samuel Blau, Brandon Wood, Shyam Dwaraknath"
__credits__ = "Xiaohui Qu"
