import socket
import tarfile
from pathlib import Path

import pytest

from custodian.utils import backup, get_execution_host_info, tracked_lru_cache


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


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        (["error.1.tar.gz", "error.3.tar"], "error.4"),
        (["error.2.tar.gz", "error.bad.tar"], "error.3"),
        (["error.foo.tar.gz"], "error.1"),
        (["error.1.tar.bz2"], "error.1"),  # matched by the glob but neither .tar nor .tar.gz
    ],
)
def test_backup_numbering(tmp_path, existing, expected) -> None:
    for name in existing:
        (tmp_path / name).write_text("")
    (tmp_path / "OUTCAR").write_text("data")

    backup(["OUTCAR"], directory=tmp_path)

    with tarfile.open(tmp_path / f"{expected}.tar.gz", "r:gz") as tar:
        assert tar.getnames() == [f"{expected}/OUTCAR"]


def test_backup_custom_prefix(tmp_path) -> None:
    (tmp_path / "INCAR").write_text("data")
    (tmp_path / "error.5.tar.gz").write_text("")  # different prefix: ignored

    backup(["INCAR"], prefix="chk", directory=tmp_path)
    backup(["INCAR"], prefix="chk", directory=tmp_path)

    assert (tmp_path / "chk.1.tar.gz").exists()
    assert (tmp_path / "chk.2.tar.gz").exists()


def test_get_execution_host_info_from_env(monkeypatch) -> None:
    monkeypatch.setenv("HOSTNAME", "node01")
    monkeypatch.setenv("SGE_O_HOST", "cluster-a")
    assert get_execution_host_info() == ("node01", "cluster-a")


def test_get_execution_host_info_falls_back_to_socket(monkeypatch) -> None:
    monkeypatch.delenv("HOSTNAME", raising=False)
    monkeypatch.delenv("SGE_O_HOST", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "socket-host")
    assert get_execution_host_info() == ("socket-host", "unknown")


def test_get_execution_host_info_unknown_when_socket_fails(monkeypatch) -> None:
    def broken():
        raise OSError("no hostname")

    monkeypatch.delenv("HOSTNAME", raising=False)
    monkeypatch.delenv("SGE_O_HOST", raising=False)
    monkeypatch.setattr(socket, "gethostname", broken)
    assert get_execution_host_info() == ("unknown", "unknown")
