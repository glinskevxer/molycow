"""Write the rules out as a document, grouped the way they are worked to.

The list in `molycow.rules` is the source. This turns it into the page that
goes on the wall, so the words a technologist reads in a refusal are the same
words the procedure manual uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

from molycow.rules import about, rules, subjects
from molycow.tools.walk import docs_root

DOCUMENT = docs_root() / "rules.md"


def lines() -> list[str]:
    """The document, built from the rule list."""
    out = [
        "# rules",
        "",
        "Every refusal this package can make, and what the rule behind it says.",
        "The short name in brackets is what a message carries in front of it and",
        "what the audit trail records.",
        "",
        f"{len(rules())} rules in {len(subjects())} groups.",
        "",
    ]
    for subject in subjects():
        out.append(f"## {subject}")
        out.append("")
        for rule in about(subject):
            out.append(f"- **{rule.code}** — {rule.says}")
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
    """Write the document, or check the one in the tree against the rule list."""
    args = sys.argv[1:] if argv is None else argv
    if "--check" not in args:
        print(f"build_rules: wrote {write()}")
        return 0
    if not DOCUMENT.exists():
        print("build_rules: docs/rules.md is missing")
        return 1
    if DOCUMENT.read_text(encoding="utf-8") != text():
        print("build_rules: docs/rules.md is out of date")
        return 1
    print("build_rules: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
