"""The layers only import downwards.

The package is a stack. Physics and units at the bottom know nothing about
records; records know nothing about sqlite; sqlite knows nothing about the
rules; the rules know nothing about printing. Every one of those sentences is
true only for as long as something checks it, because the import that breaks
it is always the convenient one.
"""

from __future__ import annotations

import ast
import sys

from molycow.tools.walk import Finding, layer_of, module_name, package_files, parse, report

BELOW: dict[str, tuple[str, ...]] = {
    "core": (),
    "model": ("core",),
    "store": ("core", "model"),
    "service": ("core", "model", "store"),
    "report": ("core", "model", "store", "service"),
    "cli": ("core", "model", "store", "service", "report"),
    "tools": ("core", "model", "store", "service", "report", "cli"),
}


def imported_modules(tree: ast.Module) -> list[tuple[str, int]]:
    """Every molycow module a file imports, with the line it is imported on."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                (alias.name, node.lineno)
                for alias in node.names
                if alias.name.startswith("molycow")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.startswith("molycow")
        ):
            found.append((node.module, node.lineno))
    return found


def layer_of_module(name: str) -> str:
    """Which layer a dotted module name belongs to."""
    parts = name.split(".")
    if len(parts) <= 2:
        return "core"
    return parts[1]


def findings() -> list[Finding]:
    """Every import that reaches sideways or upwards."""
    found: list[Finding] = []
    for path in package_files():
        here = layer_of(path)
        allowed = set(BELOW.get(here, ()))
        allowed.add(here)
        for name, line in imported_modules(parse(path)):
            if name == module_name(path):
                continue
            there = layer_of_module(name)
            if there in allowed:
                continue
            found.append(
                Finding(path, line, f"{here} imports {there} ({name})"),
            )
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_layers", findings())


if __name__ == "__main__":
    sys.exit(main())
