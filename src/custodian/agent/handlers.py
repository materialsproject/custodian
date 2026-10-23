"""AgentHandler: an ErrorHandler whose check() asks an LLM once and whose correct() applies its fix."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from pymatgen.io.vasp.inputs import VaspInput

from custodian.agent.agent import canonical_error
from custodian.custodian import ErrorHandler
from custodian.utils import backup
from custodian.vasp.handlers import VASP_BACKUP_FILES
from custodian.vasp.interpreter import VaspModder

logger = logging.getLogger(__name__)

AGENT_CHECK_SUMMARY_FILE_NAME = "custodian_agent_check.md"
AGENT_CORRECT_SUMMARY_FILE_NAME = "custodian_agent_correct.md"
_CONTCAR_COPY = {"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}}


class VaspAgentHandler(ErrorHandler):
    """Let an LLM, which can read the job directory through file tools, find and fix a VASP error."""

    def __init__(self, llm_interface, output_filename="vasp.out") -> None:
        """Initialize the handler.

        Args:
            llm_interface (LLMInterface): The LLM client that makes the decision.
            output_filename (str): Name of VASP's stdout log, given to the LLM as a hint of where to look.
        """
        self.llm_interface = llm_interface
        self.output_filename = output_filename
        self.decision: dict = {"errors": [], "actions": [], "summary": ""}
        self.proposed_actions: list = []  # what the LLM asked for, before filtering
        self.rejected_reason: str | None = None

    def check(self, directory="./") -> bool:
        """Call the LLM once and store its decision as {"errors", "actions", "summary"} in Custodian's format.

        errors are Custodian error keys (or "agent:<name>"); actions are Modder actions. An LLM failure, or an
        action list that is not allowed, counts as no error / no actions respectively.
        """
        try:
            logger.info("Start checking the files ...")
            reply = self.llm_interface.decide(directory, self.output_filename)
        except Exception:
            logger.exception("LLM decision failed; reporting no error")
            reply = {}

        self.decision = reply
        self._write_check_report(directory, self.decision)
        """
        errors = reply.get("errors") or []
        if isinstance(errors, str):
            errors = [errors]
        actions = self.proposed_actions = reply.get("actions") or []
        self.rejected_reason = _rejection(actions)
        if self.rejected_reason:
            logger.warning("Agent actions not applied: %s", self.rejected_reason)
            actions = []
        self.decision = {
            "errors": sorted({canonical_error(e) for e in errors if str(e).strip()}),
            "actions": actions,
            "summary": str(reply.get("summary") or ""),
        }
        """
        return self.decision.get("errors", False)

    def correct(self, directory="./") -> dict:
        """Apply the actions found in check() and append a report to custodian_agent.md in the directory.

        If applying raises, the failure is recorded in the report and no actions are returned, so Custodian
        stops the job instead of crashing. Empty actions make Custodian stop the job.
        """
        actions = self.decision["actions"]
        status, detail = "not applied", self.rejected_reason or "the LLM proposed no actions"
        if actions:
            try:
                backup(VASP_BACKUP_FILES | {self.output_filename}, directory=directory)
                vi = VaspInput.from_directory(directory)
                VaspModder(vi=vi, directory=directory).apply_actions(actions)
                status, detail = "applied", "apply_actions finished without error"
            except Exception as exc:
                logger.exception("Applying agent actions failed")
                status = "failed"
                detail = f"{type(exc).__name__}: {exc} (files may be partly modified; see the error.*.tar.gz backup)"
                actions = []
        self._write_correct_report(directory, status, detail)
        return {"errors": list(self.decision["errors"]), "actions": actions, "summary": self.decision["summary"]}

    def _write_check_report(self, directory, decision) -> None:
        path = os.path.join(directory, AGENT_CHECK_SUMMARY_FILE_NAME)
        try:
            n = 1
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    n += f.read().count("\n## Check ")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n## Check {n}\n")
                for key, value in decision.items():
                    f.write(f"\n#### {key}\n\n{value}\n")
        except OSError:
            logger.exception("Could not write %s", path)

    def _write_correct_report(self, directory, status, detail) -> None:
        """Append one numbered section to custodian_agent.md. A report that cannot be written never fails the job."""
        path = os.path.join(directory, AGENT_CORRECT_SUMMARY_FILE_NAME)
        try:
            n = 1
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    n += f.read().count("\n## Correction ")
            errors = "\n".join(f"- `{e}`" for e in self.decision["errors"]) or "- none"
            fix = f"```json\n{json.dumps(self.proposed_actions, indent=2)}\n```" if self.proposed_actions else "none"
            report = (
                f"\n## Correction {n} ({datetime.now().astimezone().isoformat(timespec='seconds')})\n\n"
                f"### Summary\n\n{self.decision['summary'] or self.decision['reasoning_contentor'] or 'none'}\n\n"
                f"### Identified errors\n\n{errors}\n\n"
                f"### Proposed fix\n\n{fix}\n\n"
                f"### Result\n\n**{status.capitalize()}**: {detail}\n"
            )
            with open(path, "a", encoding="utf-8") as f:
                if n == 1:
                    f.write("# Custodian agent report\n")
                f.write(report)
        except OSError:
            logger.exception("Could not write %s", path)


def _rejection(actions) -> str | None:
    """Return why the LLM's actions must not be applied, or None. The LLM may only edit INCAR/KPOINTS."""
    if not isinstance(actions, list):
        return f"actions is not a list: {actions!r}"
    for action in actions:
        if action == _CONTCAR_COPY:
            continue
        ok = (
            isinstance(action, dict)
            and set(action) == {"dict", "action"}
            and action["dict"] in ("INCAR", "KPOINTS")
            and isinstance(action["action"], dict)
            and action["action"]
            and set(action["action"]) <= {"_set", "_unset"}
            and all(isinstance(v, dict) for v in action["action"].values())
        )
        if not ok:
            return f"disallowed action: {action}"
    return None
