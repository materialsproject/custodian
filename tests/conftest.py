"""This module mocks functions needed for pytest."""

import multiprocessing
import os

import pytest
from shutil import copyfileobj

TEST_DIR = os.path.dirname(__file__)
TEST_FILES = f"{TEST_DIR}/files"


@pytest.fixture(autouse=True)
def _patch_get_potential_energy(monkeypatch) -> None:
    """Monkeypatch the multiprocessing.cpu_count() function to always return 64."""
    monkeypatch.setattr(multiprocessing, "cpu_count", lambda: 64)

def get_gzip_or_unzipped(test_file_or_dir : str) -> str:
    """ 
    Return the file or its unzipped version, depending on which one exists.

    Running pytest in CI seems to unzip the test files prior to testing.
    To get around this behavior, we return the whichever file exists,
    its gzipped version or the unzipped version.
    
    Args:
        test_file_or_dir (str) : the name of the test file or directory
    Returns:
        The file with or without a .gz/.GZ extension if any exist, or the
        unmodified path to the directory.
    """
    if os.path.isdir(test_file_or_dir):
        return test_file_or_dir
    
    for file_to_test in [test_file_or_dir, test_file_or_dir.split(".gz")[0], test_file_or_dir.split(".GZ")[0]]:
        if os.path.isfile(file_to_test):
            return file_to_test
    raise FileNotFoundError(f"Cannot find {test_file_or_dir}")