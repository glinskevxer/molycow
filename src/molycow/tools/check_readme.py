"""The readme's worked example is replayed, not trusted.

The transcript in the readme is parsed back into commands and expected output,
run against a fresh book in a temporary directory, and compared. A renamed
option, a changed number or a dropped subcommand fails here rather than
sitting in the readme misleading somebody for a year.
"""

from __future__ import annotations

import re
import shlex
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from click.testing import CliRunner

from molycow.cli.main import run
from molycow.store.migrations import latest
from molycow.tools.walk import Finding, repo_root, report

README = repo_root() / "README.md"

PROMPT = re.compile(r"^\$ molycow (.*)$")

BOOK = "day.sqlite3"


@dataclass(frozen=True)
class Step:
    """One command in the transcript and the output the readme claims for it."""

    line: int
    command: str
    expected: tuple[str, ...]


def steps() -> list[Step]:
    """Read the transcript out of the readme."""
    found: list[Step] = []
    text = README.read_text(encoding="utf-8").splitlines()
    number = 0
    while number < len(text):
        raw = text[number].rstrip()
        start = number + 1
        match = PROMPT.match(raw.strip())
        if match is None:
            number += 1
            continue
        command = match.group(1).strip()
        while command.endswith("\\") and number + 1 < len(text):
            number += 1
            command = command[:-1].strip() + " " + text[number].strip()
        expected: list[str] = []
        number += 1
        while number < len(text):
            line = text[number].rstrip()
            if not line or line.startswith(("$ ", "```")):
                break
            expected.append(line)
            number += 1
        found.append(Step(start, command, tuple(expected)))
    return found


def replay(step: Step, book: Path) -> list[str]:
    """Run one step against a book and give back what it printed."""
    args = [BOOK if part == BOOK else part for part in shlex.split(step.command)]
    args = [str(book) if part == BOOK else part for part in args]
    result = CliRunner().invoke(run, args)
    if result.exception is not None and result.exit_code != 0:
        return [f"error: {result.exception}"]
    return [line.replace(str(book), BOOK) for line in result.output.splitlines()]


def findings() -> list[Finding]:
    """Everything in the readme the build no longer agrees with."""
    found: list[Finding] = []
    text = README.read_text(encoding="utf-8")
    if f"schema {latest()}" not in text:
        found.append(Finding(README, 1, f"the readme does not quote schema {latest()}"))
    transcript = steps()
    if not transcript:
        found.append(Finding(README, 1, "the readme has no worked example in it"))
        return found
    with tempfile.TemporaryDirectory() as folder:
        book = Path(folder) / BOOK
        for step in transcript:
            printed = replay(step, book)
            for index, wanted in enumerate(step.expected):
                got = printed[index] if index < len(printed) else "<nothing>"
                if got.strip() != wanted.strip():
                    found.append(
                        Finding(
                            README,
                            step.line,
                            f"expected {wanted.strip()!r}, the command printed {got.strip()!r}",
                        )
                    )
                    break
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_readme", findings())


if __name__ == "__main__":
    sys.exit(main())
