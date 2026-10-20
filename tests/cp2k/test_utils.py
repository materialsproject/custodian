"""Tests for custodian.cp2k.utils."""

from __future__ import annotations

import shutil
from types import SimpleNamespace
from typing import Any

import pytest
from pymatgen.io.cp2k.inputs import Cp2kInput

from custodian.cp2k.interpreter import Cp2kModder
from custodian.cp2k.utils import activate_diag, activate_ot, can_use_ot, get_conv, restart, tail
from tests.cp2k.conftest import CP2K_FILES, PROGRAM_ENDED, scf_block


def _ci_without_ot() -> Cp2kInput:
    ci = Cp2kInput.from_file(f"{CP2K_FILES}/cp2k.inp.orig")
    ci.unset({"FORCE_EVAL": {"DFT": {"SCF": "OT"}}})
    return ci


def test_activate_ot() -> None:
    ci = _ci_without_ot()
    actions: list[dict[str, Any]] = [{"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"RUN_TYPE": "ENERGY"}}}}]
    activate_ot(actions, ci)

    assert len(actions) == 3
    assert actions[1]["action"] == [("_unset", {"FORCE_EVAL": {"DFT": "SCF"}})]
    scf = actions[2]["action"][0][1]["FORCE_EVAL"]["DFT"]["SCF"]
    assert scf["OT"]["MINIMIZER"] == "DIIS"
    assert scf["OT"]["PRECONDITIONER"] == "FULL_ALL"
    # The outer loop inherits the EPS_SCF of the existing input.
    assert scf["OUTER_SCF"]["EPS_SCF"] == ci["FORCE_EVAL"]["DFT"]["SCF"]["EPS_SCF"]


def test_activate_ot_applies(cp2k_dir) -> None:
    ci = _ci_without_ot()
    ci.write_file("cp2k.inp")
    actions: list = []
    activate_ot(actions, ci)
    Cp2kModder(filename="cp2k.inp").apply_actions(actions)

    new = Cp2kInput.from_file("cp2k.inp")
    assert new.check("FORCE_EVAL/DFT/SCF/OT")
    assert new["FORCE_EVAL"]["DFT"]["SCF"]["MAX_SCF"].values[0] == 20
    assert new["FORCE_EVAL"]["DFT"]["SCF"]["OT"]["LINESEARCH"].values[0] == "2PNT"
    assert new["FORCE_EVAL"]["DFT"]["SCF"]["OUTER_SCF"]["EPS_SCF"].values[0] == pytest.approx(1e-7)
    # SCF section was replaced wholesale, so SCF_GUESS from the original input is gone.
    assert new["FORCE_EVAL"]["DFT"]["SCF"].get("SCF_GUESS") is None


def test_activate_diag() -> None:
    actions: list[dict[str, Any]] = [{"dict": "cp2k.inp", "action": {"_set": {}}}]
    activate_diag(actions)

    assert len(actions) == 4
    assert actions[1]["action"] == [("_unset", {"FORCE_EVAL": {"DFT": {"SCF": "OT"}}})]
    assert actions[2]["action"] == [("_unset", {"FORCE_EVAL": {"DFT": {"SCF": "OUTER_SCF"}}})]
    [(op, settings)] = actions[3]["action"]
    assert op == "_set"
    scf = settings["FORCE_EVAL"]["DFT"]["SCF"]
    assert scf["DIAGONALIZATION"] == {}
    assert scf["SMEAR"] == {"ELEC_TEMP": 300, "METHOD": "FERMI_DIRAC"}
    assert scf["MIXING"] == {"ALPHA": 0.05}


def test_activate_diag_applies(cp2k_dir) -> None:
    actions: list = []
    activate_diag(actions)
    Cp2kModder(filename="cp2k.inp").apply_actions(actions)

    new = Cp2kInput.from_file("cp2k.inp")
    assert not new.check("FORCE_EVAL/DFT/SCF/OT")
    assert not new.check("FORCE_EVAL/DFT/SCF/OUTER_SCF")
    assert new.check("FORCE_EVAL/DFT/SCF/DIAGONALIZATION")
    assert new.by_path("FORCE_EVAL/DFT/SCF/SMEAR")["METHOD"].values[0] == "FERMI_DIRAC"


def _fake_output(band_gap):
    return SimpleNamespace(band_gap=band_gap, parse_dos=lambda: None)


@pytest.mark.parametrize(
    ("band_gap", "has_ot", "has_kpoints", "expected"),
    [
        (1.0, False, False, True),
        (0.05, False, False, False),
        (None, False, False, False),
        (1.0, True, False, False),
        (1.0, False, True, False),
    ],
)
def test_can_use_ot(band_gap, has_ot, has_kpoints, expected) -> None:
    ci = Cp2kInput.from_file(f"{CP2K_FILES}/cp2k.inp.orig") if has_ot else _ci_without_ot()
    if has_kpoints:
        ci.update({"FORCE_EVAL": {"DFT": {"KPOINTS": {"SCHEME": "MONKHORST-PACK 2 2 2"}}}})
    assert can_use_ot(_fake_output(band_gap), ci) is expected


def test_can_use_ot_custom_threshold() -> None:
    ci = _ci_without_ot()
    assert can_use_ot(_fake_output(0.5), ci, minimum_band_gap=0.4)
    assert not can_use_ot(_fake_output(0.5), ci, minimum_band_gap=0.6)


def test_tail(tmp_path) -> None:
    path = tmp_path / "f.txt"
    path.write_text("".join(f"line{i}\n" for i in range(20)))
    assert list(tail(path, 3)) == ["line17\n", "line18\n", "line19\n"]
    assert len(tail(path)) == 10
    assert tail(path, 50)[0] == "line0\n"


def test_tail_empty_file(tmp_path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("")
    assert tail(path, 4) == ["", "", "", ""]


def test_get_conv(tmp_path) -> None:
    out = tmp_path / "cp2k.out"
    out.write_text(scf_block([1e-1, 1e-2]) + scf_block([1e-3, 1e-4, 1e-5]) + PROGRAM_ENDED)
    assert get_conv(out) == pytest.approx([1e-1, 1e-2, 1e-3, 1e-4, 1e-5])


def test_get_conv_no_scf(tmp_path) -> None:
    out = tmp_path / "cp2k.out"
    out.write_text(PROGRAM_ENDED)
    assert get_conv(out) == []


def test_get_conv_fixture() -> None:
    # Line-search rows (no convergence value) are skipped.
    conv = get_conv(f"{CP2K_FILES}/cp2k.out.conv")
    assert len(conv) == 45
    assert conv[0] == pytest.approx(0.00485622)


class TestRestart:
    def test_no_actions(self, cp2k_dir) -> None:
        actions: list = []
        restart(actions, "cp2k.out", "cp2k.inp")
        assert actions == []

    def test_no_actions_needed_without_restart_file(self, cp2k_dir) -> None:
        actions: list = []
        restart(actions, "cp2k.out", "cp2k.inp", no_actions_needed=True)
        assert actions == []

    def test_restart_file_is_copied_first(self, cp2k_dir) -> None:
        shutil.copy("cp2k.inp", "CP2K-1.restart")
        actions = [{"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"RUN_TYPE": "ENERGY"}}}}]
        restart(actions, "cp2k.out", "cp2k.inp")

        assert len(actions) == 2
        assert actions[0] == {
            "file": str(cp2k_dir / "CP2K-1.restart"),
            "action": {"_file_copy": {"dest": str(cp2k_dir / "cp2k.inp")}},
        }

    @pytest.mark.parametrize(
        ("conv", "restart_file", "unset"),
        [
            ([1e-2, 1e-6], False, True),  # converged well enough: discard wfn
            ([1e-2, 1e-3], False, False),  # poorly converged and no new ionic step: keep wfn
            ([1e-2, 1e-3], True, True),  # moved on to a new ionic step: discard wfn
        ],
    )
    def test_wfn_restart(self, cp2k_dir, conv, restart_file, unset) -> None:
        ci = Cp2kInput.from_file("cp2k.inp")
        ci.update({"FORCE_EVAL": {"DFT": {"WFN_RESTART_FILE_NAME": "CP2K-RESTART.wfn"}}})
        ci.write_file("cp2k.inp")
        (cp2k_dir / "cp2k.out").write_text(scf_block(conv) + PROGRAM_ENDED)
        if restart_file:
            shutil.copy("cp2k.inp", "CP2K-1.restart")

        actions: list = []
        restart(actions, "cp2k.out", "cp2k.inp", no_actions_needed=True)
        unset_action = {"dict": "cp2k.inp", "action": {"_unset": {"FORCE_EVAL": {"DFT": "WFN_RESTART_FILE_NAME"}}}}
        assert (unset_action in actions) is unset
        assert any("file" in a for a in actions) is restart_file
