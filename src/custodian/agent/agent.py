import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from ruamel.yaml import YAML

load_dotenv()  # CBORG_API_KEY usually comes from the shell; a project .env also works

DEFAULT_MODEL = "lbl/gpt-oss-120b"
SKILLS_DIR = Path(__file__).parent / "skills" / "vasp"  # ponytail: VASP only, add per-code dirs with QChem/CP2K

SYSTEM = """You are the error-correction policy inside Custodian, which babysits VASP calculations.
A deterministic handler has detected the errors below and computed a baseline fix. Decide which fix to apply.

Options for "choice":
- "baseline": apply the baseline fix unchanged. Default when it is sensible and has not already failed in this job.
- "kb:<case_id>": reuse the actions of a past case listed under "Past runs" that resolved the same error.
- "edit": your own action list (e.g. the baseline with a different value, or a fix when the baseline is empty).

Rules for your own actions: only {"dict": "INCAR"|"KPOINTS", "action": {"_set"|"_unset": {...}}} and
{"file": "CONTCAR", "action": {"_file_copy": {"dest": "POSCAR"}}} are allowed, plus any baseline action copied
verbatim (including its file deletes). Make the smallest change that
addresses the error. Use only the information given; never invent past cases or file contents.

End your reply with exactly one fenced ```json block:
{"choice": "...", "actions": [...], "rationale": "<2-4 sentences>", "confidence": <0..1>}"""


def get_llm(model=None, temperature=0.0):
    return ChatOpenAI(
        model=model or os.getenv("LLM_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("LLM_BASE_URL", "https://api.cborg.lbl.gov"),
        api_key=os.getenv("CBORG_API_KEY"),
        temperature=temperature,
        timeout=120.0,
    )


def load_skills(errors, skills_dir=None) -> str:
    """_general.md plus every skill whose frontmatter `errors` overlaps the detected errors."""
    out = []
    for f in sorted(Path(skills_dir or SKILLS_DIR).glob("*.md")):
        _, front, body = f.read_text().split("---", 2)
        tags = YAML(typ="safe").load(front).get("errors") or []
        if f.name == "_general.md" or set(tags) & set(errors):
            out.append(body.strip())
    return "\n\n".join(out)


def decide(ctx: dict, baseline, skills: str, past: dict, model=None) -> dict:
    """One LLM call -> decision dict per the SYSTEM contract. Raises on unusable replies."""
    user = "\n\n".join([
        f"# Skill notes\n{skills}",
        f"# Context\n```json\n{json.dumps(ctx, indent=1, default=str)}\n```",
        f"# Baseline fix (built-in handler)\n```json\n{json.dumps(baseline)}\n```",
        f"# Past runs\n```json\n{json.dumps(past, indent=1)}\n```",
    ])
    reply = get_llm(model).invoke([("system", SYSTEM), ("human", user)])
    decision = extract_json(reply.text)
    if not isinstance(decision, dict):
        raise ValueError(f"no JSON decision in reply: {reply.text[:300]!r}")
    return decision


def extract_json(text: str):
    """Pull the last JSON object/array out of an LLM reply (copied from multi-agent-workflow/panel.py).
    Prefers ```json fenced blocks; falls back to the last balanced {...}/[...]."""
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