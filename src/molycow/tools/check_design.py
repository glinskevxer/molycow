"""The design note describes the package that is actually here.

A design note is worth keeping only while it matches the tree. This check
holds it to two things: every layer has a section, and every service is named
somewhere in it. A service that nobody thought worth a sentence is usually a
service that has grown somewhere it should not have.
"""

from __future__ import annotations

import sys

from molycow.tools.walk import Finding, docs_root, module_name, package_files, report, source_root

DOCUMENT = docs_root() / "design.md"


def layers() -> list[str]:
    """Every layer directory in the shipped package."""
    return sorted(
        path.name
        for path in source_root().iterdir()
        if path.is_dir() and path.name != "__pycache__"
    )


def services() -> list[str]:
    """Every service module, by its bare name."""
    return sorted(
        module_name(path).rsplit(".", 1)[1]
        for path in package_files()
        if path.parent.name == "service" and path.name != "__init__.py"
    )


def headings() -> list[str]:
    """The sections the note carries."""
    return [
        line.removeprefix("## ").strip()
        for line in DOCUMENT.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


def findings() -> list[Finding]:
    """Everything the note leaves out."""
    if not DOCUMENT.exists():
        return [Finding(DOCUMENT, 1, "there is no design note")]
    text = DOCUMENT.read_text(encoding="utf-8")
    found: list[Finding] = []
    sections = headings()
    for layer in ("core", *layers()):
        if layer not in sections:
            found.append(Finding(DOCUMENT, 1, f"the note has no section for {layer}"))
    for service in services():
        if service not in text:
            found.append(Finding(DOCUMENT, 1, f"the note does not mention the {service} service"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_design", findings())


if __name__ == "__main__":
    sys.exit(main())
