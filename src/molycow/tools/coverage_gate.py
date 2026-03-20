"""A floor under the coverage, and a floor under the worst file in it.

A single number for the whole package hides a module nobody tested behind
fifty that everybody did. This reads the json coverage writes, holds the total
to one floor and every file to a lower one, and prints the worst few either
way so the number is followed by the names behind it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from molycow.tools.walk import repo_root

REPORT = repo_root() / "coverage.json"


@dataclass(frozen=True)
class FileCoverage:
    """One file's share of covered statements."""

    name: str
    percent: float
    missing: int

    def line(self) -> str:
        """The line the gate prints for this file."""
        return f"{self.percent:6.2f}%  {self.missing:4d} missing  {self.name}"


def read(path: Path | None = None) -> tuple[float, list[FileCoverage]]:
    """The total and the per file figures out of a coverage json report."""
    target = path or REPORT
    data = json.loads(target.read_text(encoding="utf-8"))
    total = float(data["totals"]["percent_covered"])
    files = [
        FileCoverage(
            name=name,
            percent=float(body["summary"]["percent_covered"]),
            missing=int(body["summary"]["missing_lines"]),
        )
        for name, body in sorted(data["files"].items())
    ]
    return total, files


def below(files: list[FileCoverage], floor: float) -> list[FileCoverage]:
    """Every file under a floor, worst first."""
    return sorted((one for one in files if one.percent < floor), key=lambda one: one.percent)


def main(argv: list[str] | None = None) -> int:
    """Read the report, print the worst files, and hold both floors."""
    args = sys.argv[1:] if argv is None else argv
    floor = _number(args, "--floor", 90.0)
    file_floor = _number(args, "--file-floor", 80.0)
    worst = int(_number(args, "--worst", 5))
    if not REPORT.exists():
        print("coverage_gate: coverage.json is not there, run pytest --cov first")
        return 1
    total, files = read()
    for one in sorted(files, key=lambda item: item.percent)[:worst]:
        print(one.line())
    print(f"total {total:.2f}%")
    failed = False
    if total < floor:
        print(f"coverage_gate: total {total:.2f}% is under the floor of {floor:.2f}%")
        failed = True
    short = below(files, file_floor)
    for one in short:
        print(f"coverage_gate: {one.name} at {one.percent:.2f}% is under {file_floor:.2f}%")
        failed = True
    if failed:
        return 1
    print("coverage_gate: ok")
    return 0


def _number(args: list[str], flag: str, fallback: float) -> float:
    if flag not in args:
        return fallback
    index = args.index(flag)
    if index + 1 >= len(args):
        return fallback
    return float(args[index + 1])


if __name__ == "__main__":
    sys.exit(main())
