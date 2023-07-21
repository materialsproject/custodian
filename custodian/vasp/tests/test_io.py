import os
import unittest

from custodian.utils import tracked_lru_cache
from custodian.vasp.io import load_outcar, load_vasprun

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_files")


class IOTest(unittest.TestCase):
    def test_load_outcar(self):
        outcar = load_outcar(os.path.join(test_dir, "large_sigma", "OUTCAR"))
        assert outcar is not None
        outcar2 = load_outcar(os.path.join(test_dir, "large_sigma", "OUTCAR"))

        assert outcar is outcar2

        assert len(tracked_lru_cache.cached_functions) == 1

    def test_load_vasprun(self):
        vr = load_vasprun(os.path.join(test_dir, "large_sigma", "vasprun.xml"))
        assert vr is not None
        vr2 = load_vasprun(os.path.join(test_dir, "large_sigma", "vasprun.xml"))

        assert vr is vr2

        assert len(tracked_lru_cache.cached_functions) == 1
