from custodian import TEST_FILES
from custodian.utils import tracked_lru_cache
from custodian.vasp.io import load_outcar, load_vasprun


class TestIO:
    def test_load_outcar(self):
        outcar = load_outcar(f"{TEST_FILES}/large_sigma/OUTCAR")
        assert outcar is not None
        outcar2 = load_outcar(f"{TEST_FILES}/large_sigma/OUTCAR")

        assert outcar is outcar2

        assert len(tracked_lru_cache.cached_functions) == 1

    def test_load_vasprun(self):
        vr = load_vasprun(f"{TEST_FILES}/large_sigma/vasprun.xml")
        assert vr is not None
        vr2 = load_vasprun(f"{TEST_FILES}/large_sigma/vasprun.xml")

        assert vr is vr2

        assert len(tracked_lru_cache.cached_functions) == 1
