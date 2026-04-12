"""Every command says what it does, and every group is reachable from the root.

A command with no help line is a command nobody outside the pharmacy can use,
and a group that was written but never added to the root group is a command
nobody can reach at all. Both have happened here, which is why this reads the
command tree rather than the source.
"""

from __future__ import annotations

import sys
from importlib import import_module

import click

from molycow.cli.main import run
from molycow.tools.walk import Finding, report, source_root

CLI_ROOT = source_root() / "cli"


def walk(group: click.Group, prefix: str = "") -> list[tuple[str, click.Command]]:
    """Every command under a group, with the words that reach it."""
    found: list[tuple[str, click.Command]] = []
    for name, command in sorted(group.commands.items()):
        path = f"{prefix} {name}".strip()
        found.append((path, command))
        if isinstance(command, click.Group):
            found.extend(walk(command, path))
    return found


def group_modules() -> list[str]:
    """The command modules in the package, by file name."""
    return sorted(
        path.stem
        for path in CLI_ROOT.glob("*.py")
        if path.stem not in {"__init__", "main", "session"}
    )


def groups_defined_in(module_name: str) -> list[click.Group]:
    """The command groups one module defines.

    A module is not required to name its group after itself. ``register``
    carries both ``customer`` and ``physician``, so the check compares the
    group objects rather than the file names.
    """
    module = import_module(f"molycow.cli.{module_name}")
    return [
        value
        for name, value in vars(module).items()
        if isinstance(value, click.Group) and not name.startswith("_")
    ]


def findings() -> list[Finding]:
    """Every command with no help, and every group the root does not carry."""
    found: list[Finding] = []
    carried = set(run.commands.values())
    for path, command in walk(run):
        if not (command.help or command.short_help):
            found.append(Finding(CLI_ROOT / "main.py", 1, f"'{path}' has no help line"))
    for module in group_modules():
        defined = groups_defined_in(module)
        if defined and not any(one in carried for one in defined):
            found.append(
                Finding(
                    CLI_ROOT / f"{module}.py",
                    1,
                    f"the {module} commands are not on the root group",
                )
            )
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_cli", findings())


if __name__ == "__main__":
    sys.exit(main())
