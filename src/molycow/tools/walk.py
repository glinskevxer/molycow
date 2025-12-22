"""Finding the source this repository is made of, for the checks to read."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    """The top of the checkout, found from this file rather than from the cwd."""
    return Path(__file__).resolve().parents[3]


def source_root() -> Path:
    """The shipped package inside the checkout."""
    return repo_root() / "src" / "molycow"


def tests_root() -> Path:
    """The test suite inside the checkout."""
    return repo_root() / "tests"


def docs_root() -> Path:
    """The generated documents inside the checkout."""
    return repo_root() / "docs"


def source_files(under: Path | None = None) -> list[Path]:
    """Every shipped python file, in a stable order."""
    root = under or source_root()
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    )


def package_files() -> list[Path]:
    """Every shipped python file including the package markers."""
    return sorted(path for path in source_root().rglob("*.py") if "__pycache__" not in path.parts)


def suite_files() -> list[Path]:
    """Every test module, in a stable order."""
    return sorted(
        path for path in tests_root().rglob("test_*.py") if "__pycache__" not in path.parts
    )


def module_name(path: Path) -> str:
    """The dotted name a shipped file is imported as."""
    relative = path.resolve().relative_to(source_root().parent)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def layer_of(path: Path) -> str:
    """Which layer a shipped file belongs to."""
    relative = path.resolve().relative_to(source_root())
    if len(relative.parts) == 1:
        return "core"
    return relative.parts[0]


@dataclass(frozen=True)
class Finding:
    """One thing a check objects to."""

    path: Path
    line: int
    message: str

    def format(self, root: Path | None = None) -> str:
        where = self.path
        base = root or repo_root()
        if where.is_absolute():
            where = where.relative_to(base)
        return f"{where}:{self.line}: {self.message}"


def parse(path: Path) -> ast.Module:
    """Read a file into a syntax tree."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


Definition = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def public_definitions(tree: ast.Module) -> Iterator[Definition]:
    """Every public class, function and method in a module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            yield node


def report(name: str, findings: list[Finding]) -> int:
    """Print what a check found and give back the exit status it wants."""
    for finding in findings:
        print(finding.format())
    if findings:
        print(f"{name}: {len(findings)} findings")
        return 1
    print(f"{name}: ok")
    return 0
