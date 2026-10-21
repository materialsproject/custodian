"""LLMInterface: the LLM client, skill notes, prompt and decision call used by AgentHandler."""

import json
import os
import re
from pathlib import Path

from monty.json import MSONable
from ruamel.yaml import YAML

from custodian.vasp.handlers import AliasingErrorHandler, LrfCommutatorHandler, StdErrHandler, VaspErrorHandler

DEFAULT_MODEL = "lbl/gpt-oss-120b"
SKILLS_DIR = Path(__file__).parent / "skills" / "vasp"  # ponytail: VASP only, add per-code dirs with QChem/CP2K

SYSTEM_RULES = """You are the error-correction policy inside Custodian, which babysits VASP calculations.
You get a summary of a VASP run that just stopped: Custodian error keys whose log text appears
(known_errors_in_log), the WARNING/ERROR messages in the log with counts, INCAR, numbers parsed from OSZICAR,
OUTCAR, vasprun.xml and the structure, the log tail, corrections already applied in this job, and skill notes.
vasprun.xml is incomplete when the run was killed; it then has no convergence flags or band gap.
Sometimes a built-in handler has also detected errors and computed a baseline fix.
Decide whether the run hit an error that needs an input change, and if so which fix to apply.

Options for "choice":
- "none": nothing to fix. Return empty "errors" and "actions".
- "baseline": apply the baseline fix unchanged. Default when one is given, it is sensible, and it has not
  already failed in this job.
- "kb:<case_id>": reuse the actions of a past case listed under "Past runs" that resolved the same error.
- "edit": your own action list (e.g. the baseline with a different value, or a fix when there is no baseline).

Rules for your own actions: only {"dict": "INCAR"|"KPOINTS", "action": {"_set"|"_unset": {...}}} and
{"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}} are allowed, plus any baseline action copied
verbatim (including its file deletes). Make the smallest change that addresses the error. Use only the
information given; never invent past cases or file contents.

End your reply with exactly one fenced ```json block:
{"errors": ["<Custodian error keys>"], "choice": "...", "actions": [...], "rationale": "<2-4 sentences>",
 "confidence": <0..1>}"""


def _error_msgs() -> dict[str, list[str]]:
    """Custodian's VASP error keys and the log texts that trigger them, read from the handlers themselves."""
    out: dict[str, list[str]] = {}
    for h in (VaspErrorHandler, StdErrHandler, LrfCommutatorHandler, AliasingErrorHandler):
        for key, msgs in h.error_msgs.items():
            out.setdefault(key, []).extend(msgs)  # grad_not_orth is in both VaspErrorHandler and StdErrHandler
    out.pop("auto_nbands")  # warning only: VaspErrorHandler.check never reports it
    return out


ERROR_MSGS = _error_msgs()
ERROR_TABLE = "\n".join(f"- {key}: {' | '.join(msgs)}" for key, msgs in sorted(ERROR_MSGS.items()))

SYSTEM = (
    SYSTEM_RULES
    + "\n\nName each error with one of Custodian's error keys below, exactly as written. Report a key only when "
    "one of its log texts appears in the logs you were given. For an error that matches none of them, use "
    '"agent:<short_snake_case_name>".\n\n'
    "Custodian error keys (key: log text that triggers it):\n" + ERROR_TABLE
)


def canonical_error(name) -> str:
    """Map an LLM error name onto Custodian's key, ignoring case; anything else becomes agent:<snake_case_name>."""
    key = str(name).strip()
    if key.lower() in ERROR_MSGS:  # Custodian's keys are all lowercase
        return key.lower()
    if key.lower().startswith("agent:"):
        key = key[len("agent:") :]
    return "agent:" + re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


class LLMInterface(MSONable):
    """Ask an LLM on an OpenAI-compatible API (LBNL CBorg by default) how to fix a VASP run.

    Only settings are stored, so the object serializes with its handler into custodian.json and job specs.
    The chat client is created on first use and the API key is read from $CBORG_API_KEY, never stored.
    """

    def __init__(self, model=None, base_url=None, temperature=0.0, timeout=120.0, skills_dir=None) -> None:
        """Initialize the settings.

        Args:
            model (str): Model name. Defaults to $LLM_MODEL, then DEFAULT_MODEL.
            base_url (str): API endpoint. Defaults to $LLM_BASE_URL, then CBorg.
            temperature (float): Sampling temperature.
            timeout (float): Seconds to wait for one reply.
            skills_dir (str): Directory of skill notes. Defaults to the bundled VASP notes.
        """
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.cborg.lbl.gov")
        self.temperature = temperature
        self.timeout = timeout
        self.skills_dir = skills_dir
        self._llm = None

    @property
    def llm(self):
        """The langchain chat client, created on first use."""
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=os.getenv("CBORG_API_KEY"),
                temperature=self.temperature,
                timeout=self.timeout,
            )
        return self._llm

    def load_skills(self, errors=None) -> str:
        """Return _general.md plus the skill notes whose frontmatter `errors` overlap errors (all if None)."""
        out: list[str] = []
        for f in sorted(Path(self.skills_dir or SKILLS_DIR).glob("*.md")):
            _, front, body = f.read_text().split("---", 2)
            tags = YAML(typ="safe").load(front).get("errors") or []
            if errors is None or f.name == "_general.md" or set(tags) & set(errors):
                out.append(body.strip())
        return "\n\n".join(out)

    def decide(self, ctx: dict, baseline=None, past=None) -> dict:
        """Make one LLM call and return its decision. Raises on unusable replies.

        Args:
            ctx (dict): Run state. If it has "errors", only those skill notes are sent; otherwise all of them.
            baseline (list): Actions a built-in handler would apply, if any.
            past (dict): Similar past cases, if any.

        Returns:
            dict: {"errors", "choice", "actions", "rationale", "confidence"}.
        """
        user = "\n\n".join(
            [
                f"# Skill notes\n{self.load_skills(ctx.get('errors'))}",
                f"# Context\n```json\n{json.dumps(ctx, indent=1, default=str)}\n```",
                f"# Baseline fix (built-in handler)\n```json\n{json.dumps(baseline)}\n```",
                f"# Past runs\n```json\n{json.dumps(past or {}, indent=1)}\n```",
            ]
        )
        reply = self.llm.invoke([("system", SYSTEM), ("human", user)])
        decision = self.extract_json(reply.text)
        if not isinstance(decision, dict):
            raise ValueError(f"no JSON decision in reply: {reply.text[:300]!r}")
        return decision

    @staticmethod
    def extract_json(text: str):
        """Pull the last JSON object/array out of an LLM reply.

        Prefers ```json fenced blocks; falls back to the last balanced {...}/[...].
        """
        fences = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
        for block in reversed(fences):
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                pass
        pairs = sorted(  # try whichever bracket appears first, so [{...}] parses as a list
            (("{", "}"), ("[", "]")),
            key=lambda p: text.find(p[0]) if text.find(p[0]) != -1 else len(text),
        )
        for opener, closer in pairs:
            start = text.find(opener)
            while start != -1:
                depth = 0
                for i in range(start, len(text)):
                    if text[i] == opener:
                        depth += 1
                    elif text[i] == closer:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[start : i + 1])
                            except json.JSONDecodeError:
                                break
                start = text.find(opener, start + 1)
        return None
