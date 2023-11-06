"""
This module mocks functions needed for pytest.
"""
import multiprocessing

import pytest


@pytest.fixture(autouse=True)
def _patch_get_potential_energy(monkeypatch):
    """
    Monkeypatch the multiprocessing.cpu_count() function to always return 64
    """
    monkeypatch.setattr(multiprocessing, "cpu_count", lambda *args, **kwargs: 64)


@pytest.fixture(autouse=True)
def _clear_tracked_cache():
    """
    Clear the cache of the stored functions between the tests.
    """
    from custodian.utils import tracked_lru_cache

    tracked_lru_cache.tracked_cache_clear()
