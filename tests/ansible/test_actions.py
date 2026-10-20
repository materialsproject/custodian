from __future__ import annotations

import os
import stat

import pytest

from custodian.ansible.actions import FileActions


@pytest.mark.parametrize(
    ("action", "match"),
    [
        (FileActions.file_create, "content"),
        (FileActions.file_move, "dest"),
        (FileActions.file_delete, "mode"),
    ],
)
def test_single_setting_actions_reject_multiple_settings(tmp_path, monkeypatch, action, match) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f").write_text("x")
    with pytest.raises(ValueError, match=match):
        action("f", {"a": 1, "b": 2}, str(tmp_path))
    assert (tmp_path / "f").read_text() == "x"


def test_file_delete_simulated_keeps_file(tmp_path, capsys) -> None:
    (tmp_path / "f").write_text("x")
    FileActions.file_delete("f", {"mode": "simulated"}, str(tmp_path))
    assert (tmp_path / "f").exists()
    assert "Simulated removal of f" in capsys.readouterr().out


def test_file_delete_missing_file_is_ignored(tmp_path) -> None:
    FileActions.file_delete("missing", {"mode": "actual"}, str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_file_move_and_copy_use_directory(tmp_path) -> None:
    (tmp_path / "src").write_text("data")
    FileActions.file_copy("src", {"dest1": "a", "dest2": "b"}, str(tmp_path))
    FileActions.file_move("src", {"dest": "moved"}, str(tmp_path))
    assert {p.name for p in tmp_path.iterdir()} == {"a", "b", "moved"}
    assert (tmp_path / "moved").read_text() == "data"


def test_file_modify_mode(tmp_path) -> None:
    (tmp_path / "f").write_text("x")
    FileActions.file_modify("f", {"mode": 0o600}, str(tmp_path))
    assert stat.S_IMODE((tmp_path / "f").stat().st_mode) == 0o600


@pytest.mark.xfail(
    strict=True,
    reason="actions.py:234 file_create opens `filename` relative to the CWD and ignores `directory`.",
)
def test_file_create_uses_directory(tmp_path, monkeypatch) -> None:
    cwd = tmp_path / "cwd"
    target = tmp_path / "target"
    cwd.mkdir()
    target.mkdir()
    monkeypatch.chdir(cwd)
    FileActions.file_create("f", {"content": "hello"}, str(target))
    assert not (cwd / "f").exists()
    assert (target / "f").read_text() == "hello"


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX ownership only")
@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="actions.py:305 calls os.chown(path, val) with a single owner argument, which always raises TypeError.",
)
def test_file_modify_owners(tmp_path) -> None:
    (tmp_path / "f").write_text("x")
    owners = (os.getuid(), os.getgid())
    FileActions.file_modify("f", {"owners": owners}, str(tmp_path))
    st = (tmp_path / "f").stat()
    assert (st.st_uid, st.st_gid) == owners
