import os
import unittest

from custodian import ROOT
from custodian.utils import tracked_lru_cache
from custodian.vasp.io import load_outcar, load_vasprun

TEST_DIR = f"{ROOT}/tests/files"


class IOTest(unittest.TestCase):
    def test_load_outcar(self):
        outcar = load_outcar(os.path.join(TEST_DIR, "large_sigma", "OUTCAR"))
        assert outcar is not None
        outcar2 = load_outcar(os.path.join(TEST_DIR, "large_sigma", "OUTCAR"))

        assert outcar is outcar2

        assert len(tracked_lru_cache.cached_functions) == 1

    def test_load_vasprun(self):
        vr = load_vasprun(os.path.join(TEST_DIR, "large_sigma", "vasprun.xml"))
        assert vr is not None
        vr2 = load_vasprun(os.path.join(TEST_DIR, "large_sigma", "vasprun.xml"))

        assert vr is vr2

        assert len(tracked_lru_cache.cached_functions) == 1
