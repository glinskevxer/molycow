"""Nothing shipped is unreachable.

A module with green tests and no caller is not finished work, it is a draft
that passes. Every shipped module has to be reachable from the command line,
from a check, or from something that is. Anything else is either dead or was
meant to be wired in and never was.
"""

from __future__ import annotations

import sys

from molycow.tools.check_layers import imported_modules
from molycow.tools.walk import Finding, module_name, package_files, parse, report

ENTRY_POINTS = ("molycow", "molycow.cli.main")

TOOL_PREFIX = "molycow.tools."


def graph() -> dict[str, set[str]]:
    """What every shipped module imports, by dotted name."""
    edges: dict[str, set[str]] = {}
    for path in package_files():
        name = module_name(path)
        edges[name] = {found for found, _ in imported_modules(parse(path))}
    return edges


def reachable() -> set[str]:
    """Every module reachable from an entry point or a check."""
    edges = graph()
    seen: set[str] = set()
    queue = [one for one in edges if one in ENTRY_POINTS or one.startswith(TOOL_PREFIX)]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        for imported in edges.get(name, set()):
            if imported in edges and imported not in seen:
                queue.append(imported)
            parent = imported.rsplit(".", 1)[0]
            if parent in edges and parent not in seen:
                queue.append(parent)
    return seen


def findings() -> list[Finding]:
    """Every shipped module nothing reaches."""
    live = reachable()
    found: list[Finding] = []
    for path in package_files():
        name = module_name(path)
        if name in live:
            continue
        found.append(Finding(path, 1, f"{name} is not reachable from anything"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_wiring", findings())


if __name__ == "__main__":
    sys.exit(main())
