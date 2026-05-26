"""Test names are sentences, and nothing in the suite is numbered.

A test called ``test_dose_2`` tells whoever reads the failure nothing at all.
Every test in this suite says what should be true, in words, so a red build
reads as a sentence about the pharmacy rather than as a coordinate.
"""

from __future__ import annotations

import ast
import re
import sys

from molycow.tools.walk import Finding, package_files, parse, report, suite_files

NUMBERED = re.compile(r"_\d+$")

SHORTEST = 4

VERBS = ("test_a_", "test_an_", "test_the_", "test_every_", "test_no_", "test_nothing_")


def test_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Every test function in a module, with the line it starts on."""
    return [
        (node.name, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    ]


def findings() -> list[Finding]:
    """Every name that would read badly in a failure line."""
    found: list[Finding] = []
    for path in suite_files():
        for name, line in test_names(parse(path)):
            if NUMBERED.search(name):
                found.append(Finding(path, line, f"{name} is numbered rather than named"))
                continue
            words = name.removeprefix("test_").split("_")
            if len(words) < SHORTEST:
                found.append(Finding(path, line, f"{name} is not a sentence"))
    for path in package_files():
        if path.stem != path.stem.lower():
            found.append(Finding(path, 1, "module names are lower case"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_naming", findings())


if __name__ == "__main__":
    sys.exit(main())
