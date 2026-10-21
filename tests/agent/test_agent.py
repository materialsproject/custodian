import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from monty.json import MontyDecoder, MontyEncoder
from pymatgen.io.vasp.inputs import Incar

from custodian.agent.agent import ERROR_MSGS, SYSTEM, LLMInterface, canonical_error
from custodian.agent.handlers import AgentHandler
from custodian.vasp.handlers import StdErrHandler, VaspErrorHandler
from tests.conftest import TEST_FILES

AMIX = [{"dict": "INCAR", "action": {"_set": {"AMIX": 0.05}}}]


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def invoke(self, messages):
        if isinstance(self.reply, Exception):
            raise self.reply
        return SimpleNamespace(text=self.reply)


def handler(decision):
    iface = LLMInterface(model="test-model")
    iface._llm = FakeLLM(decision if isinstance(decision, Exception) else f"ok\n```json\n{json.dumps(decision)}\n```")
    return AgentHandler(iface, output_filename="vasp.brmix")


@pytest.fixture
def run_dir(tmp_path):
    for f in Path(TEST_FILES).iterdir():
        if f.is_file():
            shutil.copy(f, tmp_path)
    return tmp_path


def test_check_then_correct_applies_valid_fix(run_dir):
    h = handler({"errors": ["brmix"], "choice": "edit", "actions": AMIX, "rationale": "r", "confidence": 0.8})
    assert h.check(directory=run_dir)
    out = h.correct(directory=run_dir)
    assert out["errors"] == ["brmix"]
    assert out["actions"] == AMIX
    assert out["agent"]["rejected_reason"] is None
    assert Incar.from_file(run_dir / "INCAR")["AMIX"] == 0.05
    assert list(run_dir.glob("error.*.tar.gz"))


@pytest.mark.parametrize(
    "actions",
    [
        [{"dict": "POTCAR", "action": {"_set": {"symbols": ["Fe"]}}}],
        [{"dict": "INCAR", "action": {"_set": {"NOT_A_TAG": 1}}}],
        [{"dict": "INCAR", "action": {"_unset": {"NOT_SET": 1}}}],
        [{"file": "POSCAR", "action": {"_file_delete": {"mode": "actual"}}}],
        [],
    ],
)
def test_unsafe_or_empty_actions_are_not_applied(run_dir, actions):
    incar_before = (run_dir / "INCAR").read_text()
    h = handler({"errors": ["brmix"], "choice": "edit", "actions": actions})
    assert h.check(directory=run_dir)
    out = h.correct(directory=run_dir)
    assert out["actions"] == []  # Custodian stops the job on empty actions
    assert out["agent"]["rejected_reason"]
    assert (run_dir / "INCAR").read_text() == incar_before
    assert (run_dir / "POSCAR").exists()


def test_llm_error_names_map_to_custodian_keys(run_dir):
    names = ["BRMIX", " ZBRENT ", "Charge Sloshing", "agent:Odd-Thing", ""]
    h = handler({"errors": names, "choice": "edit", "actions": AMIX})
    assert h.check(directory=run_dir)
    assert h.errors == {"brmix", "zbrent", "agent:charge_sloshing", "agent:odd_thing"}
    assert h.correct(directory=run_dir)["errors"] == ["agent:charge_sloshing", "agent:odd_thing", "brmix", "zbrent"]
    assert handler({"errors": "BRMIX", "choice": "edit", "actions": AMIX}).check(directory=run_dir)
    assert canonical_error("brmix") == "brmix"


def test_prompt_lists_custodian_error_keys():
    assert "- brmix: BRMIX: very serious problems" in SYSTEM
    assert "auto_nbands" not in ERROR_MSGS  # Custodian only warns about it
    assert all(key == key.lower() for key in ERROR_MSGS)  # canonical_error relies on this
    both = VaspErrorHandler.error_msgs["grad_not_orth"] + StdErrHandler.error_msgs["grad_not_orth"]
    assert set(both) <= set(ERROR_MSGS["grad_not_orth"])
    assert set(VaspErrorHandler.error_msgs) - {"auto_nbands"} <= set(ERROR_MSGS)


@pytest.mark.parametrize("decision", [{"errors": [], "choice": "none", "actions": []}, RuntimeError("CBorg down")])
def test_no_error_or_llm_failure_reports_no_error(run_dir, decision):
    assert not handler(decision).check(directory=run_dir)


def test_handler_roundtrips_without_api_key(monkeypatch):
    monkeypatch.setenv("CBORG_API_KEY", "secret-key-value")
    h = AgentHandler(LLMInterface(model="test-model", skills_dir="/skills"), kb_path="kb.jsonl")
    dumped = json.dumps(h, cls=MontyEncoder)
    assert "secret-key-value" not in dumped
    h2 = json.loads(dumped, cls=MontyDecoder)
    assert isinstance(h2, AgentHandler)
    assert isinstance(h2.llm_interface, LLMInterface)
    assert (h2.llm_interface.model, h2.llm_interface.skills_dir, h2.kb_path) == ("test-model", "/skills", "kb.jsonl")


def test_load_skills_and_extract_json(tmp_path):
    (tmp_path / "_general.md").write_text("---\nerrors: []\n---\nGENERAL")
    (tmp_path / "brmix.md").write_text("---\nerrors: [brmix]\n---\nBRMIX")
    (tmp_path / "zbrent.md").write_text("---\nerrors: [zbrent]\n---\nZBRENT")
    iface = LLMInterface(skills_dir=str(tmp_path))
    assert iface.load_skills(["brmix"]) == "GENERAL\n\nBRMIX"
    assert iface.load_skills() == "GENERAL\n\nBRMIX\n\nZBRENT"
    assert LLMInterface.extract_json('x ```json\n{"a": 1}\n``` y') == {"a": 1}
    assert LLMInterface.extract_json('reply {"b": [1, 2]} end') == {"b": [1, 2]}
