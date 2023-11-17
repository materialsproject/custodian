"""This module mocks functions needed for pytest."""

import multiprocessing

import pytest


@pytest.fixture(autouse=True)
def _patch_get_potential_energy(monkeypatch):
    """Monkeypatch the multiprocessing.cpu_count() function to always return 64."""
    monkeypatch.setattr(multiprocessing, "cpu_count", lambda *args, **kwargs: 64)
