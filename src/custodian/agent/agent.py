"""LLMInterface: the LLM client, skill notes, prompt and decision call used by AgentHandler."""

import json
import logging
import os
import re
import textwrap
from pathlib import Path

from langchain_core.messages import ToolMessage, convert_to_openai_messages
from monty.json import MSONable

from custodian.agent.toolkit import FileManagementToolkit
from custodian.vasp.handlers import AliasingErrorHandler, LrfCommutatorHandler, StdErrHandler, VaspErrorHandler

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "lbl/gpt-oss-120b"
# DEFAULT_MODEL = "gpt-6-sol"
SKILLS_DIR = Path(__file__).parent / "skills" / "vasp"  # ponytail: VASP only, add per-code dirs with QChem/CP2K

SYSTEM_RULES = """You are the error-correction policy inside Custodian, which babysits VASP calculations.
A VASP run in the job directory just stopped. You are given the directory listing and the name of VASP's log file.
You have read-only file tools: list_files, read_file, tail_file, grep_file. Use them to find out what went wrong:
decide from the listing which files matter (e.g. the end of the log, INCAR, KPOINTS, OSZICAR, grep OUTCAR for the
failing step, an older error.*.tar.gz listing, custodian.json for corrections already applied) and read only those,
with as few calls as you can. Prefer tail_file/grep_file over reading whole files. POTCAR and bulk binary files
(WAVECAR, CHGCAR, ...) are not available. vasprun.xml is incomplete when the run was killed.
Decide whether the run hit an error that needs an input change, and if so which fix to apply. If a correction
was already applied for the same error, do not repeat it; try something different or give no actions.

Rules for "actions" (Custodian's Modder format): only
{"dict": "INCAR"|"KPOINTS", "action": {"_set"|"_unset": {...}}} and
{"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}} are allowed.
Make the smallest change that addresses the error. Use only what you read; never invent file contents.
If nothing needs fixing, return empty "errors" and "actions".

When you have enough evidence, stop calling file tools and call the Decision tool. Do not write the decision as text.
- Nothing wrong with the run: errors and actions both empty.
- A problem exists but you can't find a safe fix, or the evidence is incomplete: report the error key (or
  "agent:inconclusive") with empty actions, and use the summary to say what you checked and what is missing.
Always call Decision, even when unsure."""


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

    def __init__(
        self, model=None, base_url=None, temperature=0.0, timeout=300.0, skills_dir=None, max_tool_rounds=100
    ) -> None:
        """Initialize the settings.

        Args:
            model (str): Model name. Defaults to $LLM_MODEL, then DEFAULT_MODEL.
            base_url (str): API endpoint. Defaults to $LLM_BASE_URL, then CBorg.
            temperature (float): Sampling temperature.
            timeout (float): Seconds to wait for one reply.
            skills_dir (str): Directory of skill notes. Defaults to the bundled VASP notes.
            max_tool_rounds (int): Most rounds of file-tool calls the LLM gets per decision.
        """
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.cborg.lbl.gov")
        self.temperature = temperature
        self.timeout = timeout
        self.skills_dir = skills_dir
        self.max_tool_rounds = max_tool_rounds
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

    @llm.setter
    def llm(self, chat_model) -> None:
        """Use any langchain chat model that supports bind_tools instead of the default ChatOpenAI client."""
        self._llm = chat_model

    def _strip_frontmatter(self, text: str) -> str:
        """Drop an optional leading '---' YAML block; notes without one are returned unchanged."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                return parts[2]
        return text

    def load_skills(self) -> str:
        """Return every skill note (*.md) in the skills directory, joined with blank lines."""
        folder = Path(self.skills_dir or SKILLS_DIR)
        notes = [self._strip_frontmatter(f.read_text()).strip() for f in sorted(folder.glob("*.md"))]
        if not notes:
            logger.warning("No skill notes found in %s", folder)
        return "\n\n".join(notes)

    def decide(self, directory, output_filename="vasp.out") -> dict:
        """Ask the LLM what went wrong in a job directory and how to fix it. Raises on unusable replies.

        The LLM sees the skill notes and the directory listing, and may read files through the
        FileManagementToolkit tools for up to max_tool_rounds rounds.

        Args:
            directory (str): The job directory.
            output_filename (str): VASP's log file name, passed as a hint.

        Returns:
            dict: {"errors", "actions", "summary"} as written by the LLM (not validated).
        """
        toolkit = FileManagementToolkit(directory)
        user = "\n\n".join(
            [
                f"# Skill notes\n{self.load_skills()}",
                f"# Job directory\nVASP log file: {output_filename}\n```\n{toolkit.list_files()}\n```",
            ]
        )
        reply = self._run_tools([("system", SYSTEM), ("human", user)], toolkit)

        try:
            decision = self.extract_json(reply.content)
            if not isinstance(decision, dict):
                return {}
            # raise ValueError(f"no JSON decision in reply: {reply.content[:300]!r}")
        except:
            return {}
        return decision

    def _run_tools(self, messages: list, toolkit: FileManagementToolkit):
        """Let the LLM call the file tools until it answers without one or the round budget runs out.

        When the budget is spent the LLM is asked once more, with no tools bound, for its decision.
        Returns the final reply.
        """
        logger.info("=" * 60)
        logger.info(f"Prompt:\n{messages}")
        logger.info(textwrap.indent(str(messages), "\t"))

        tools = {t.name: t for t in toolkit.get_tools()}
        llm = self.llm.bind_tools(list(tools.values()))

        for _ in range(self.max_tool_rounds):
            reply = llm.invoke(messages)
            logger.info("=" * 30)
            logger.info("pre-tools reoponse:\n")
            logger.info(textwrap.indent(str(reply), "\t"))
            if not reply.tool_calls:
                logger.info("=" * 15)
                logger.warning("No tools_calls")
                return reply
            messages.append(reply)
            for cidx, call in enumerate(reply.tool_calls):
                tool = tools.get(call["name"])
                out = tool.invoke(call["args"]) if tool else f"ERROR: unknown tool {call['name']!r}"
                logger.info("=" * 30)
                logger.info(f"Using Tool calling {cidx}: {tool}. Response:")
                logger.info(textwrap.indent(str(out), "\t"))
                messages.append(ToolMessage(content=str(out), tool_call_id=call["id"]))
        logger.info("=" * 60)
        logger.info("Final Prompt:\n")
        logger.info(textwrap.indent(str(messages), "\t"))
        logger.info("=" * 60)

        final_reply = self.llm.invoke(messages)
        logger.info("Final response:\n")
        logger.info(textwrap.indent(str(final_reply), "\t"))
        logger.info("=" * 60)

        if final_reply.content:
            return final_reply

        # An OpenAI-compatible server (here gpt-oss on vLLM) sometimes returns an empty `content`: the
        # model's output can end up only in a provider-specific field such as `reasoning_content`.
        # LangChain's `ChatOpenAI` keeps only the standard OpenAI fields and drops the rest, so `invoke`
        # looks empty. We therefore call the underlying client directly
        # (`ChatOpenAI.root_client.chat.completions.create`). The raw response keeps the extra fields in
        # `choices[0].message.model_extra`, so we can see what the model produced and store its reasoning
        # alongside its decision.

        raw = self.llm.root_client.chat.completions.create(
            model=self.model,
            messages=convert_to_openai_messages(messages),
            temperature=self.temperature,
        )
        choice = raw.choices[0]
        extras = choice.message.model_extra or {}
        reasoning = (
            extras.get("reasoning_content")
            or extras.get("reasoning")
            or (extras.get("provider_specific_fields") or {}).get("reasoning")
            or ""
        )
        logger.info(f"Final reasonign: {reasoning}")

        return extras

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
