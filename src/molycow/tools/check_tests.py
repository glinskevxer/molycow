"""Every shipped module is imported by the test suite by name.

Coverage says a line ran. It does not say anybody wrote a test about the
module that line is in, because a module can be dragged along by a test of
something else and come out fully covered without ever being the thing under
test. This check asks the narrower question: does any test file import it.
"""

from __future__ import annotations

import ast
import sys

from molycow.tools.check_layers import imported_modules
from molycow.tools.walk import (
    Finding,
    module_name,
    package_files,
    parse,
    report,
    suite_files,
    tests_root,
)

EXEMPT = frozenset({"molycow"})


def imported_by_tests() -> set[str]:
    """Every package module the suite imports, including through a package.

    ``from molycow.tools import check_layers`` imports a module even though the
    dotted name never appears, so the alias is joined onto the package it came
    from as well.
    """
    seen: set[str] = set()
    for path in suite_files():
        tree = parse(path)
        for name, _ in imported_modules(tree):
            seen.add(name)
            parts = name.split(".")
            for depth in range(2, len(parts)):
                seen.add(".".join(parts[:depth]))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if not node.module.startswith("molycow"):
                    continue
                for alias in node.names:
                    seen.add(f"{node.module}.{alias.name}")
    return seen


def driven_through_the_cli(name: str) -> bool:
    """A command group is tested by the file that drives its commands.

    The command modules are never imported by name. They are reached through
    the root group, so the suite exercises ``molycow.cli.kit`` by running
    ``kit compound`` in ``tests/cli/test_kit_commands.py``.
    """
    if not name.startswith("molycow.cli."):
        return False
    group = name.rsplit(".", 1)[1]
    return (tests_root() / "cli" / f"test_{group}_commands.py").exists()


def findings() -> list[Finding]:
    """Every shipped module no test file names."""
    tested = imported_by_tests()
    found: list[Finding] = []
    for path in package_files():
        name = module_name(path)
        if name in EXEMPT or name in tested or driven_through_the_cli(name):
            continue
        found.append(Finding(path, 1, f"{name} is not imported by any test"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_tests", findings())


if __name__ == "__main__":
    sys.exit(main())
