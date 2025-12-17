import pytest
from monty.os.path import zpath

from custodian.utils import tracked_lru_cache
from custodian.vasp.io import load_outcar, load_vasprun
from tests.conftest import TEST_FILES


@pytest.fixture(autouse=True)
def _clear_tracked_cache() -> None:
    """Clear the cache of the stored functions between the tests."""
    tracked_lru_cache.tracked_cache_clear()


class TestIO:
    def test_load_outcar(self) -> None:
        outcar_file = zpath(f"{TEST_FILES}/io/OUTCAR")
        outcar = load_outcar(outcar_file)
        assert outcar is not None
        outcar2 = load_outcar(outcar_file)

        assert outcar is outcar2

        assert len(tracked_lru_cache.cached_functions) == 1

    def test_load_vasprun(self) -> None:
        vasprun_file = zpath(f"{TEST_FILES}/io/vasprun.xml")
        vr = load_vasprun(vasprun_file)
        assert vr is not None
        vr2 = load_vasprun(vasprun_file)

        assert vr is vr2

        assert len(tracked_lru_cache.cached_functions) == 1
