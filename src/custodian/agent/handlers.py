"""AgentHandler: an ErrorHandler whose check() and correct() ask an LLMInterface."""

import json
import logging
import warnings
from pathlib import Path

from pymatgen.io.vasp.inputs import BadIncarWarning, Incar

from custodian.agent.agent import canonical_error
from custodian.custodian import ErrorHandler
from custodian.utils import backup
from custodian.vasp.handlers import VASP_BACKUP_FILES
from custodian.vasp.interpreter import VaspModder

logger = logging.getLogger(__name__)

_CONTCAR_COPY = {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}


class AgentHandler(ErrorHandler):
    """Let an LLM find the error in a stopped VASP run and choose its fix.

    is_monitor stays False, so check() runs once after each VASP run instead of on every poll.
    """

    def __init__(self, llm_interface, kb_path=None, output_filename="vasp.out") -> None:
        """Initialize the handler.

        Args:
            llm_interface (LLMInterface): Makes the decisions.
            kb_path (str): kb.jsonl with past cases. Not read yet.
            output_filename (str): File VASP's stdout is redirected to.
        """
        self.llm_interface = llm_interface
        self.kb_path = kb_path
        self.output_filename = output_filename
        self.errors: set[str] = set()
        self.decision: dict = {}

    def check(self, directory="./"):
        """Ask the LLM whether the run hit an error that needs an input change. LLM failures count as no error."""
        try:
            self.decision = self.llm_interface.decide(read_context(directory, self.output_filename))
        except Exception:
            logger.exception("LLM decision failed; reporting no error")
            self.decision = {}
        errors = self.decision.get("errors") or []
        if isinstance(errors, str):
            errors = [errors]
        self.errors = {canonical_error(e) for e in errors if str(e).strip()}
        return bool(self.errors)

    def correct(self, directory="./"):
        """Apply the actions chosen in check() if they validate; empty actions make Custodian stop the job."""
        decision = self.decision or self.llm_interface.decide(read_context(directory, self.output_filename))
        llm_actions = decision.get("actions") or []
        reason = validate(llm_actions, directory)
        actions = [] if reason else llm_actions
        if actions:
            backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
            VaspModder(directory=directory).apply_actions(actions)
        self.decision = {}
        return {
            "errors": sorted(self.errors),
            "actions": actions,
            "agent": {
                "model": self.llm_interface.model,
                "choice": decision.get("choice"),
                "rationale": decision.get("rationale"),
                "confidence": decision.get("confidence"),
                "llm_actions": llm_actions,
                "rejected_reason": reason,
            },
        }


def read_context(directory, output_filename="vasp.out") -> dict:
    """Collect what the LLM sees: INCAR, KPOINTS, log tails and the corrections already applied in this job.

    ponytail: log tails only; grep VaspErrorHandler.error_msgs if errors scroll out of the last 40 lines.
    """
    d = Path(directory)
    ctx: dict = {}
    if (d / "INCAR").exists():
        ctx["incar"] = dict(Incar.from_file(d / "INCAR"))
    if (d / "KPOINTS").exists():
        ctx["kpoints"] = (d / "KPOINTS").read_text()
    for name, n in ((output_filename, 40), ("OSZICAR", 10)):
        if (d / name).exists():
            ctx[f"{name}_tail"] = (d / name).read_text(errors="replace").splitlines()[-n:]
    try:  # Custodian rewrites custodian.json after every check
        corrections = json.loads((d / "custodian.json").read_text())[-1]["corrections"]
    except (OSError, ValueError, LookupError):
        corrections = []
    ctx["prior_corrections"] = [{"errors": c.get("errors"), "actions": c.get("actions")} for c in corrections]
    return ctx


def validate(actions, directory):
    """Return a reason string if actions are unsafe to apply, else None. This is the trust boundary."""
    if not isinstance(actions, list) or not actions:
        return "no actions"
    modder = None
    for a in actions:
        if a == _CONTCAR_COPY:
            continue
        ok = (
            isinstance(a, dict)
            and set(a) == {"dict", "action"}
            and a["dict"] in ("INCAR", "KPOINTS")
            and isinstance(a["action"], dict)
            and a["action"]
            and set(a["action"]) <= {"_set", "_unset"}
            and all(isinstance(v, dict) for v in a["action"].values())
        )
        if not ok:
            return f"disallowed action: {a}"
        if a["dict"] == "INCAR" and "_set" in a["action"]:
            with warnings.catch_warnings():
                warnings.simplefilter("error", BadIncarWarning)
                try:
                    Incar(a["action"]["_set"]).check_params()
                except BadIncarWarning as w:
                    return f"bad INCAR value: {w}"
        modder = modder or VaspModder(directory=directory)
        try:  # in-memory only: modify_object returns a new object, nothing is written
            modder.modify_object(a["action"], modder.vi[a["dict"]])
        except Exception as exc:
            return f"action does not apply: {a} ({exc})"
    return None
