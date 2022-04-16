"""
This module mocks functions needed for pytest.
"""
import multiprocessing
import pytest


def mock_cpu_count(*args, **kwargs):
    # Instead of running multiprocessing.cpu_count(), we return a fixed
    # value during tests
    return 64


@pytest.fixture(autouse=True)
def patch_get_potential_energy(monkeypatch):
    # Monkeypatch the multiprocessing.cpu_count() function
    monkeypatch.setattr(multiprocessing, "cpu_count", mock_cpu_count)
