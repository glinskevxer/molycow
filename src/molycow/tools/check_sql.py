"""Sql lives in the store and nowhere else.

A service that writes its own query is a service that has to be read twice:
once for the rule it is applying and once for the shape of the table it is
reading. Every statement in this package is in a repository, where the table
it touches is the table that repository is about.
"""

from __future__ import annotations

import ast
import re
import sys

from molycow.tools.walk import Finding, layer_of, package_files, parse, report

STATEMENT = re.compile(
    r"\b(SELECT\b[\s\S]*?\bFROM"
    r"|INSERT\s+INTO"
    r"|UPDATE\b[\s\S]*?\bSET"
    r"|DELETE\s+FROM"
    r"|CREATE\s+TABLE"
    r"|CREATE\s+INDEX"
    r"|ALTER\s+TABLE)\b",
    re.IGNORECASE,
)

ALLOWED_LAYERS = frozenset({"store"})

ALLOWED_FILES = frozenset({"tools/check_sql.py", "tools/check_indexes.py", "tools/schema_dump.py"})


def strings_in(tree: ast.Module) -> list[tuple[str, int]]:
    """Every string constant in a file, with the line it starts on."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append((node.value, node.lineno))
    return found


def findings() -> list[Finding]:
    """Every sql statement written outside the store."""
    found: list[Finding] = []
    for path in package_files():
        relative = "/".join(path.parts[-2:])
        if layer_of(path) in ALLOWED_LAYERS or relative in ALLOWED_FILES:
            continue
        for text, line in strings_in(parse(path)):
            match = STATEMENT.search(text)
            if match is None:
                continue
            verb = match.group(0).split()[0].lower()
            found.append(Finding(path, line, f"sql outside the store: {verb}"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_sql", findings())


if __name__ == "__main__":
    sys.exit(main())
