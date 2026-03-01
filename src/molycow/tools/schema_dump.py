"""Write the schema out as a document, and check the one in the tree matches.

The document is generated from a book built by the migrations, so it cannot
drift from what the code actually creates. ``--check`` is what ci runs: it
rebuilds the document and compares, and a migration that ships without the
document being rebuilt fails there rather than in a code review.
"""

from __future__ import annotations

import sys
from pathlib import Path

from molycow.store import Book
from molycow.store.migrations import apply, latest
from molycow.tools.walk import docs_root

DOCUMENT = docs_root() / "schema.md"


def lines() -> list[str]:
    """The document, built from a book this function makes itself."""
    out = [
        "# schema",
        "",
        f"Generated from the migrations. Schema version {latest()}.",
        "",
    ]
    with Book.in_memory() as book:
        apply(book)
        for table in book.tables():
            out.append(f"## {table}")
            out.append("")
            for column in book.all(f"PRAGMA table_info({table})"):
                flags = []
                if int(column["pk"]) > 0:
                    flags.append("primary key")
                if int(column["notnull"]) == 1:
                    flags.append("not null")
                note = f" ({', '.join(flags)})" if flags else ""
                out.append(f"- `{column['name']}` {column['type']}{note}")
            keys = book.all(f"PRAGMA foreign_key_list({table})")
            for key in keys:
                out.append(f"- `{key['from']}` points at `{key['table']}.{key['to']}`")
            indexes = [
                str(row["name"])
                for row in book.all(f"PRAGMA index_list({table})")
                if not str(row["name"]).startswith("sqlite_")
            ]
            if indexes:
                out.append(f"- indexes: {', '.join(sorted(indexes))}")
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
        target = write()
        print(f"schema_dump: wrote {target}")
        return 0
    if not DOCUMENT.exists():
        print("schema_dump: docs/schema.md is missing")
        return 1
    if DOCUMENT.read_text(encoding="utf-8") != text():
        print("schema_dump: docs/schema.md does not match the migrations")
        return 1
    print("schema_dump: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
