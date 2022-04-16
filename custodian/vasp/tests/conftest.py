import multiprocessing
import pytest


def mock_cpu_count(self, **kwargs):
    # Instead of running multiprocessing.cpu_count(), we return a fixed
    # value during tests
    return 64


@pytest.fixture(autouse=True)
def patch_get_potential_energy(monkeypatch):
    # Monkeypatch the multiprocessing.cpu_count() function
    monkeypatch.setattr(multiprocessing, "cpu_count", mock_cpu_count)
