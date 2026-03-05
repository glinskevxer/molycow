"""Write the glossary document, and check the one in the tree matches.

The prose comes from the term list in the package, and the tables underneath
it are generated from the nuclide table and the formulary, so a kit added to
the formulary appears in the glossary without anybody remembering to add it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from molycow.formulary import known as monographs
from molycow.glossary import terms
from molycow.nuclides import known as nuclides
from molycow.tools.walk import docs_root

DOCUMENT = docs_root() / "glossary.md"


def lines() -> list[str]:
    """The document, built from the package's own tables."""
    out = ["# glossary", "", "The words this pharmacy uses, and what they mean here.", ""]
    for term in terms():
        out.append(term.line())
        out.append("")
    out.append("## nuclides on the licence")
    out.append("")
    out.append("| symbol | half life (h) | used for |")
    out.append("| --- | --- | --- |")
    for row in nuclides():
        out.append(f"| {row.symbol} | {row.half_life_hours} | {row.use.value} |")
    out.append("")
    out.append("## kits compounded here")
    out.append("")
    out.append("| code | product | made with | purity floor |")
    out.append("| --- | --- | --- | --- |")
    for kit in monographs():
        out.append(f"| {kit.code} | {kit.name} | {kit.nuclide} | {kit.rcp_floor}% |")
    out.append("")
    return out


def text() -> str:
    """The whole document as one string."""
    return "\n".join(lines()) + "\n"


def write(path: Path | None = None) -> Path:
    """Put the document in the tree."""
    target = path or DOCUMENT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text(), encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    """Write the document, or check the one in the tree against a fresh build."""
    args = sys.argv[1:] if argv is None else argv
    if "--check" not in args:
        print(f"build_glossary: wrote {write()}")
        return 0
    if not DOCUMENT.exists():
        print("build_glossary: docs/glossary.md is missing")
        return 1
    if DOCUMENT.read_text(encoding="utf-8") != text():
        print("build_glossary: docs/glossary.md is out of date")
        return 1
    print("build_glossary: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
