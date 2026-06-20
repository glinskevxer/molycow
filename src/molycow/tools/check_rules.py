"""Every rule a service can refuse on is written down in one list.

A rule invented inside a service and never added to `molycow.rules` is a rule
nobody outside the source knows exists. The check reads the refusals out of the
tree and compares them against the list, in both directions: a rule in the list
that nothing raises is just as wrong.
"""

from __future__ import annotations

import ast
import sys

from molycow.rules import BY_CODE
from molycow.tools.walk import Finding, package_files, parse, report, source_root

REFUSALS = frozenset({"RuleError", "SafetyError", "ReleaseError"})


def raised_codes() -> dict[str, tuple[str, int]]:
    """Every rule code the tree raises, with where it is raised."""
    found: dict[str, tuple[str, int]] = {}
    for path in package_files():
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in REFUSALS or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.setdefault(first.value, (str(path), node.lineno))
    return found


def findings() -> list[Finding]:
    """Every rule the list and the tree disagree about."""
    from pathlib import Path

    raised = raised_codes()
    listed = set(BY_CODE)
    found: list[Finding] = []
    for code, (path, line) in sorted(raised.items()):
        if code not in listed:
            found.append(Finding(Path(path), line, f"{code} is refused on and not written down"))
    for code in sorted(listed - set(raised)):
        found.append(
            Finding(source_root() / "rules.py", 1, f"{code} is written down and never refused on")
        )
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_rules", findings())


if __name__ == "__main__":
    sys.exit(main())
