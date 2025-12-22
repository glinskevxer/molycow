"""Every shipped module and every public name in it carries a docstring.

The rule is not decoration. Half the domain in this package is a rule with a
reason behind it, and the reason lives in the docstring or it lives nowhere.

Modules, classes and free functions are held to it without exception. A method
is held to it when it can refuse: anything that raises is applying a rule, and
a rule that is not written down is one the next person has to reconstruct from
the code. A method that only reads and returns is covered by the docstring on
its own class.
"""

from __future__ import annotations

import ast
import sys

from molycow.tools.walk import Finding, package_files, parse, public_definitions


def findings() -> list[Finding]:
    """Everything in the shipped source with no docstring on it."""
    found: list[Finding] = []
    for path in package_files():
        tree = parse(path)
        if ast.get_docstring(tree) is None:
            found.append(Finding(path, 1, "module has no docstring"))
        methods = _method_names(tree)
        for node in public_definitions(tree):
            if ast.get_docstring(node) is not None:
                continue
            if _is_dunder(node):
                continue
            if node.name in methods and not _makes_a_decision(node):
                continue
            found.append(Finding(path, node.lineno, f"{node.name} has no docstring"))
    return found


def _method_names(tree: ast.Module) -> set[str]:
    """The names defined inside a class rather than at module level."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for member in node.body:
            if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(member.name)
    return names


def _is_dunder(node: ast.AST) -> bool:
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    return node.name.startswith("__") and node.name.endswith("__")


def _makes_a_decision(node: ast.AST) -> bool:
    """Whether a method can refuse, which is a rule worth writing down."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    return any(isinstance(inner, ast.Raise) for inner in ast.walk(node))


def main() -> int:
    """Run the check and give back the status ci should see."""
    from molycow.tools.walk import report

    return report("check_docstrings", findings())


if __name__ == "__main__":
    sys.exit(main())
