import tarfile
from pathlib import Path

from custodian.utils import backup, tracked_lru_cache


def test_cache_and_clear() -> None:
    n_calls = 0

    @tracked_lru_cache
    def some_func(x):
        nonlocal n_calls
        n_calls += 1
        return x

    assert some_func(1) == 1
    assert n_calls == 1
    assert some_func(2) == 2
    assert n_calls == 2
    assert some_func(1) == 1
    assert n_calls == 2

    assert len(tracked_lru_cache.cached_functions) == 1

    tracked_lru_cache.tracked_cache_clear()

    assert len(tracked_lru_cache.cached_functions) == 0

    assert some_func(1) == 1
    assert n_calls == 3


def test_backup(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with open("INCAR", "w") as f:
        f.write("This is a test file.")

    backup(["INCAR"])

    assert Path("error.1.tar.gz").exists()
    with tarfile.open("error.1.tar.gz", "r:gz") as tar:
        assert len(tar.getmembers()) == 1
        assert tar.getnames() == ["error.1/INCAR"]


def test_backup_with_glob(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with open("INCAR", "w") as f:
        f.write("This is a test file.")
    with open("POSCAR", "w") as f:
        f.write("This is a test file.")
    with open("garbage", "w") as f:
        f.write("This is a test file.")

    backup(["*CAR"])

    assert Path("error.1.tar.gz").exists()
    with tarfile.open("error.1.tar.gz", "r:gz") as tar:
        assert len(tar.getmembers()) == 2
        assert set(tar.getnames()) == {"error.1/INCAR", "error.1/POSCAR"}


def test_backup_with_directory(tmp_path) -> None:
    with open(tmp_path / "INCAR", "w") as f:
        f.write("This is a test file.")

    backup(["INCAR"], directory=tmp_path)

    assert Path(tmp_path / "error.1.tar.gz").exists()
    with tarfile.open(tmp_path / "error.1.tar.gz", "r:gz") as tar:
        assert len(tar.getmembers()) == 1
        assert tar.getnames() == ["error.1/INCAR"]
