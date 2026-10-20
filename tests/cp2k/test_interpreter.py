"""Tests for the CP2K Modder."""

from __future__ import annotations

import shutil

import pytest
from pymatgen.io.cp2k.inputs import Cp2kInput

from custodian.cp2k.interpreter import Cp2kModder


@pytest.fixture
def modder(cp2k_dir) -> Cp2kModder:
    return Cp2kModder(filename="cp2k.inp")


def test_init_reads_input(cp2k_dir) -> None:
    modder = Cp2kModder(filename="cp2k.inp", directory=str(cp2k_dir))
    assert modder.ci.check("FORCE_EVAL/DFT/SCF/OT")
    ci = Cp2kInput.from_file("cp2k.inp")
    assert Cp2kModder(filename="cp2k.inp", ci=ci).ci is ci


def test_apply_dict_set_and_unset(modder) -> None:
    modder.apply_actions(
        [
            {"dict": "cp2k.inp", "action": {"_set": {"FORCE_EVAL": {"DFT": {"SCF": {"MAX_SCF": 99}}}}}},
            {"dict": "cp2k.inp", "action": {"_unset": {"FORCE_EVAL": {"DFT": {"SCF": "OUTER_SCF"}}}}},
        ]
    )
    ci = Cp2kInput.from_file("cp2k.inp")
    assert ci["FORCE_EVAL"]["DFT"]["SCF"]["MAX_SCF"].values[0] == 99
    assert not ci.check("FORCE_EVAL/DFT/SCF/OUTER_SCF")


def test_apply_list_of_tuples(modder) -> None:
    modder.apply_actions(
        [
            {
                "dict": "cp2k.inp",
                "action": [
                    ("_set", {"GLOBAL": {"RUN_TYPE": "ENERGY"}}),
                    ("_set", {"GLOBAL": {"PROJECT_NAME": "TEST"}}),
                ],
            }
        ]
    )
    ci = Cp2kInput.from_file("cp2k.inp")
    assert ci["GLOBAL"]["RUN_TYPE"].values[0] == "ENERGY"
    assert ci["GLOBAL"]["PROJECT_NAME"].values[0] == "TEST"


def test_modify_skips_key_errors() -> None:
    class Raiser:
        def __init__(self) -> None:
            self.calls: list = []

        def unset(self, settings):
            raise KeyError(settings)

        def set(self, settings):
            self.calls.append(settings)

    obj = Raiser()
    Cp2kModder._modify({"_unset": {"A": "B"}, "_set": {"C": 1}}, obj)
    assert obj.calls == [{"C": 1}]


def test_apply_file_action_reloads_input(modder, cp2k_dir) -> None:
    alt = Cp2kInput.from_file("cp2k.inp")
    alt.update({"GLOBAL": {"RUN_TYPE": "GEO_OPT"}})
    alt.write_file("alt.inp")
    modder.apply_actions(
        [
            {"file": "alt.inp", "action": {"_file_copy": {"dest": "cp2k.inp"}}},
            {"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"PROJECT_NAME": "AFTER"}}}},
        ]
    )
    assert modder.ci["GLOBAL"]["RUN_TYPE"].values[0] == "GEO_OPT"
    ci = Cp2kInput.from_file("cp2k.inp")
    assert ci["GLOBAL"]["RUN_TYPE"].values[0] == "GEO_OPT"
    assert ci["GLOBAL"]["PROJECT_NAME"].values[0] == "AFTER"


def test_apply_unrecognized_action(modder) -> None:
    with pytest.raises(ValueError, match="Unrecognized format"):
        modder.apply_actions([{"bogus": "cp2k.inp", "action": {}}])


def test_apply_in_other_directory(tmp_path, cp2k_dir) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    shutil.copy("cp2k.inp", run_dir / "cp2k.inp")
    Cp2kModder(filename="cp2k.inp", directory=str(run_dir)).apply_actions(
        [{"dict": "cp2k.inp", "action": {"_set": {"GLOBAL": {"PROJECT_NAME": "SUB"}}}}]
    )
    assert Cp2kInput.from_file(run_dir / "cp2k.inp")["GLOBAL"]["PROJECT_NAME"].values[0] == "SUB"
    assert Cp2kInput.from_file("cp2k.inp")["GLOBAL"]["PROJECT_NAME"].values[0] == "CP2K"
