"""FileManagementToolkit: read-only file tools that let the LLM pull in the files it needs from a job directory."""

from __future__ import annotations

import functools
import logging
import re
from collections import deque
from pathlib import Path

from monty.io import zopen
from monty.os.path import zpath

logger = logging.getLogger(__name__)

# VASP files that are never shown to the LLM: POTCAR is license-restricted, the rest are huge binary or volumetric data
DENIED_PREFIXES = (
    "POTCAR",
    "WAVECAR",
    "WAVEDER",
    "TMPCAR",
    "CHGCAR",
    "CHG",
    "AECCAR",
    "ELFCAR",
    "LOCPOT",
    "PARCHG",
)
_COMPRESSION_SUFFIXES = (".gz", ".bz2", ".xz", ".z")


class FileManagementToolkit:
    """Sandboxed, read-only file tools for one job directory.

    Every path is resolved inside `directory` (no `..`, no symlinks pointing out), compressed files (.gz, .bz2, ...)
    are read transparently, and each reply is capped in lines and characters so one call cannot flood the context.
    Tools never raise: a problem comes back as an "ERROR: ..." string the LLM can react to.
    """

    def __init__(self, directory, max_chars=15000, max_lines=300, max_line_chars=300, max_listing=200) -> None:
        """Initialize the toolkit.

        Args:
            directory (str): The job directory every path is relative to.
            max_chars (int): Cap on the characters in one tool reply.
            max_lines (int): Cap on the lines one read/tail call may return.
            max_line_chars (int): Longer lines are cut to this many characters.
            max_listing (int): Cap on the entries list_files returns.
        """
        self.directory = Path(directory).resolve()
        self.max_chars = max_chars
        self.max_lines = max_lines
        self.max_line_chars = max_line_chars
        self.max_listing = max_listing

    def get_tools(self) -> list:
        """Return the tools as langchain StructuredTools, ready for `llm.bind_tools`."""
        from langchain_core.tools import StructuredTool

        return [
            StructuredTool.from_function(func=self._safe(fn), name=fn.__name__, description=fn.__doc__)
            for fn in (self.list_files, self.read_file, self.tail_file, self.grep_file)
        ]

    def list_files(self, subdir: str = ".") -> str:
        """List the files and folders in the job directory (or a sub-folder of it) with their sizes in bytes.

        Use this first to see which files exist, e.g. whether OUTCAR, vasprun.xml or an earlier error.*.tar.gz is there.
        """
        folder = self._resolve(subdir)
        if not folder.is_dir():
            return f"ERROR: {subdir!r} is not a directory"
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name))
        rows = [
            f"{p.name}/" if p.is_dir() else f"{p.name}  {p.stat().st_size}" + ("  (not readable)" if _denied(p) else "")
            for p in entries[: self.max_listing]
        ]
        if len(entries) > self.max_listing:
            rows.append(f"... {len(entries) - self.max_listing} more entries not shown")
        return "\n".join(rows) or "(empty directory)"

    def read_file(self, path: str, start_line: int = 1, num_lines: int = 100) -> str:
        """Read a text file (INCAR, KPOINTS, OSZICAR, OUTCAR, vasp.out, ...) starting at a 1-based line number.

        Returns at most `num_lines` numbered lines. For large files prefer grep_file or tail_file; page through
        with start_line when you really need more.
        """
        file = self._text_file(path)
        start, n = max(1, start_line), min(max(1, num_lines), self.max_lines)
        out, total = [], 0
        with zopen(file, mode="rb") as f:
            for total, raw in enumerate(f, start=1):
                if total >= start + n:
                    break
                if total >= start:
                    out.append(self._fmt(total, raw))
        if not out:
            return f"(no lines at or after line {start}; the file has {total} lines)"
        return self._cap("\n".join(out), more=total >= start + n)

    def tail_file(self, path: str, num_lines: int = 50) -> str:
        """Read the last `num_lines` lines of a text file. Best for the end of vasp.out, OSZICAR or OUTCAR."""
        file = self._text_file(path)
        n = min(max(1, num_lines), self.max_lines)
        last: deque = deque(maxlen=n)  # ponytail: streams the whole file; fine for OUTCARs, slow for multi-GB logs
        with zopen(file, mode="rb") as f:
            for i, raw in enumerate(f, start=1):
                last.append(self._fmt(i, raw))
        return self._cap("\n".join(last) or "(empty file)")

    def grep_file(
        self, path: str, pattern: str, ignore_case: bool = False, context: int = 0, max_matches: int = 30
    ) -> str:
        """Search a text file with a regular expression and return matching lines with their line numbers.

        `context` adds that many lines (0-5) before and after each match. Good for finding WARNING/ERROR messages,
        'reached required accuracy', 'F=' lines or a specific INCAR tag in a large file.
        """
        file = self._text_file(path)
        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            return f"ERROR: invalid regular expression: {exc}"
        context, max_matches = min(max(0, context), 5), min(max(1, max_matches), 100)
        before: deque = deque(maxlen=context)
        out: list[str] = []
        matches = after = 0
        with zopen(file, mode="rb") as f:
            for i, raw in enumerate(f, start=1):
                line = self._fmt(i, raw)
                if rx.search(raw.decode(errors="replace")):
                    matches += 1
                    if matches > max_matches:
                        out.append(f"... more matches after line {i - 1}; narrow the pattern or raise max_matches")
                        break
                    if out and before.maxlen and len(before) == context and after == 0:
                        out.append("--")
                    out.extend(before)
                    before.clear()
                    out.append(line)
                    after = context
                elif after:
                    out.append(line)
                    after -= 1
                else:
                    before.append(line)
        return self._cap("\n".join(out) or f"no match for {pattern!r}")

    def _safe(self, fn):
        """Wrap a tool so any failure becomes an ERROR string and every call is logged."""

        @functools.wraps(fn)  # langchain builds the tool's argument schema from the wrapped signature
        def wrapper(*args, **kwargs):
            logger.info("agent tool %s %s %s", fn.__name__, args, kwargs)
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                return f"ERROR: {type(exc).__name__}: {exc}"[:300]

        return wrapper

    def _resolve(self, path) -> Path:
        """Resolve path inside the job directory, falling back to a compressed twin (INCAR -> INCAR.gz)."""
        target = (self.directory / str(path)).resolve()
        if not target.is_relative_to(self.directory):
            raise ValueError(f"{path!r} is outside the job directory")
        return Path(zpath(str(target)))

    def _text_file(self, path) -> Path:
        """Resolve path to an existing, permitted, non-binary file or raise ValueError."""
        file = self._resolve(path)
        if not file.is_file():
            raise ValueError(f"{path!r} does not exist or is not a file; use list_files")
        if _denied(file):
            raise ValueError(f"{file.name} is not available (license-restricted or bulk binary data)")
        with zopen(file, mode="rb") as f:
            if b"\0" in f.read(1024):
                raise ValueError(f"{file.name} is a binary file")
        return file

    def _fmt(self, number: int, raw: bytes) -> str:
        text = raw.decode(errors="replace").rstrip("\r\n")
        if len(text) > self.max_line_chars:
            text = text[: self.max_line_chars] + f"... [{len(text) - self.max_line_chars} more chars]"
        return f"{number}: {text}"

    def _cap(self, text: str, more: bool = False) -> str:
        if len(text) > self.max_chars:
            return text[: self.max_chars] + "\n... [output truncated; ask for fewer lines or use grep_file]"
        return text + ("\n... [more lines follow]" if more else "")


def _denied(path: Path) -> bool:
    name = path.name.upper()
    for suffix in _COMPRESSION_SUFFIXES:
        name = name.removesuffix(suffix.upper())
    return name.startswith(DENIED_PREFIXES)
