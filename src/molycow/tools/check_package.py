"""What has to be true of the thing that gets installed.

The package is typed all the way through and says so with a `py.typed`
marker, or every project that installs it gets no types at all and nobody
finds out. The console script has to point at something that exists, and the
wheel has to carry the package without carrying the test suite.
"""

from __future__ import annotations

import sys
import tomllib
from importlib import import_module

from molycow.tools.walk import Finding, repo_root, report, source_root

PYPROJECT = repo_root() / "pyproject.toml"

MARKER = source_root() / "py.typed"


def settings() -> dict[str, object]:
    """The pyproject, read once."""
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def scripts() -> dict[str, str]:
    """The console scripts the package declares."""
    project = settings().get("project", {})
    assert isinstance(project, dict)
    found = project.get("scripts", {})
    return {str(name): str(target) for name, target in found.items()}


def packaged() -> list[str]:
    """The directories the wheel is built from."""
    tool = settings().get("tool", {})
    assert isinstance(tool, dict)
    hatch = tool.get("hatch", {})
    build = hatch.get("build", {}).get("targets", {}).get("wheel", {})
    return [str(one) for one in build.get("packages", [])]


def findings() -> list[Finding]:
    """Everything about the installable package that is not right."""
    found: list[Finding] = []
    if not MARKER.exists():
        found.append(Finding(MARKER, 1, "the package does not ship a py.typed marker"))
    declared = scripts()
    if "molycow" not in declared:
        found.append(Finding(PYPROJECT, 1, "there is no molycow console script"))
    for name, target in declared.items():
        module_name, _, attribute = target.partition(":")
        try:
            module = import_module(module_name)
        except ImportError:
            found.append(Finding(PYPROJECT, 1, f"{name} points at a module that is not there"))
            continue
        if not hasattr(module, attribute):
            found.append(Finding(PYPROJECT, 1, f"{name} points at {target}, which is not there"))
    if packaged() != ["src/molycow"]:
        found.append(Finding(PYPROJECT, 1, "the wheel does not carry exactly the package"))
    project = settings().get("project", {})
    assert isinstance(project, dict)
    if not str(project.get("description", "")).strip():
        found.append(Finding(PYPROJECT, 1, "the package has no description"))
    if "click" not in " ".join(str(one) for one in project.get("dependencies", [])):
        found.append(Finding(PYPROJECT, 1, "the package does not declare what it needs"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_package", findings())


if __name__ == "__main__":
    sys.exit(main())
