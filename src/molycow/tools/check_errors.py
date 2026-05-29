"""Every refusal reads the same way, and every error class is actually used.

The messages in this package are lower case, have no full stop, and say what
is wrong rather than what the code was doing. They end up in front of a
technologist mid morning, so a message that reads like a stack trace is a
message that costs somebody a telephone call.

An error class nobody raises is worse than none: it looks like a case that is
handled and is not.
"""

from __future__ import annotations

import ast
import sys

from molycow import errors as error_module
from molycow.tools.walk import Finding, package_files, parse, report

ALLOWED_ENDINGS = ("?",)


def error_classes() -> list[str]:
    """Every error class the package defines."""
    return [
        name
        for name, value in vars(error_module).items()
        if isinstance(value, type) and issubclass(value, error_module.MolycowError)
    ]


def raised_messages() -> list[tuple[str, str, int, ast.Module]]:
    """Every literal message this package raises, with where it was raised."""
    found: list[tuple[str, str, int, ast.Module]] = []
    for path in package_files():
        tree = parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            call = node.exc
            texts = [
                one.value
                for one in call.args
                if isinstance(one, ast.Constant) and isinstance(one.value, str)
            ]
            if not texts:
                continue
            found.append((str(path), texts[-1], node.lineno, tree))
    return found


def raised_classes() -> set[str]:
    """Every error class the package builds.

    Building rather than raising, because one of them is built in a helper and
    raised by its caller, and a class that is built is a class in use.
    """
    names: set[str] = set()
    for path in package_files():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def findings() -> list[Finding]:
    """Every message that does not read like the others, and every unused class."""
    from pathlib import Path

    found: list[Finding] = []
    for path, message, line, _ in raised_messages():
        if not message:
            found.append(Finding(Path(path), line, "an empty message"))
            continue
        if message[0].isupper():
            found.append(Finding(Path(path), line, f"message starts upper case: {message!r}"))
        if message.endswith(".") or (
            message[-1] in {"!", ";"} and message[-1] not in ALLOWED_ENDINGS
        ):
            found.append(Finding(Path(path), line, f"message ends in punctuation: {message!r}"))
    raised = raised_classes()
    for name in error_classes():
        if name in {"MolycowError"}:
            continue
        if name not in raised:
            found.append(
                Finding(
                    Path(error_module.__file__ or "errors.py"),
                    1,
                    f"{name} is defined and never raised",
                )
            )
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_errors", findings())


if __name__ == "__main__":
    sys.exit(main())
