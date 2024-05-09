import pytest

from custodian.utils import tracked_lru_cache
from custodian.vasp.io import load_outcar, load_vasprun
from tests.conftest import TEST_FILES


@pytest.fixture(autouse=True)
def _clear_tracked_cache() -> None:
    """Clear the cache of the stored functions between the tests."""
    from custodian.utils import tracked_lru_cache

    tracked_lru_cache.tracked_cache_clear()


class TestIO:
    def test_load_outcar(self) -> None:
        outcar = load_outcar(f"{TEST_FILES}/large_sigma/OUTCAR")
        assert outcar is not None
        outcar2 = load_outcar(f"{TEST_FILES}/large_sigma/OUTCAR")

        assert outcar is outcar2

        assert len(tracked_lru_cache.cached_functions) == 1

    def test_load_vasprun(self) -> None:
        vr = load_vasprun(f"{TEST_FILES}/large_sigma/vasprun.xml.1")
        assert vr is not None
        vr2 = load_vasprun(f"{TEST_FILES}/large_sigma/vasprun.xml.1")

        assert vr is vr2

        assert len(tracked_lru_cache.cached_functions) == 1
