"""Every foreign key has an index behind it.

Sqlite indexes the parent side of a key for free, because the parent side is a
primary key. It does not index the child side. That means every join and every
cascade over a key with no index of its own is a table scan, and it stays a
table scan quietly until the book has a season in it.

Only the leading column of a key is asked for. A key over two columns is
served by an index on the first of them, and asking for the second as well
would demand an index that no query would ever use.

The check builds a fresh book from the migrations and reads the schema back
out of sqlite rather than out of the migration text, so an index dropped by a
later migration is caught too.
"""

from __future__ import annotations

import sys

from molycow.store import Book
from molycow.store.migrations import apply
from molycow.tools.walk import Finding, repo_root, report

MIGRATIONS_FILE = repo_root() / "src" / "molycow" / "store" / "migrations.py"


def covered_columns(book: Book, table: str) -> set[str]:
    """The columns an index or a primary key already puts first."""
    covered: set[str] = set()
    for index in book.all(f"PRAGMA index_list({table})"):
        columns = book.all(f"PRAGMA index_info({index['name']})")
        if columns:
            covered.add(str(columns[0]["name"]))
    for column in book.all(f"PRAGMA table_info({table})"):
        if int(column["pk"]) == 1:
            covered.add(str(column["name"]))
    return covered


def findings() -> list[Finding]:
    """Every child side of a foreign key with nothing indexing it."""
    found: list[Finding] = []
    with Book.in_memory() as book:
        apply(book)
        for table in book.tables():
            covered = covered_columns(book, table)
            for key in book.all(f"PRAGMA foreign_key_list({table})"):
                if int(key["seq"]) != 0:
                    continue
                column = str(key["from"])
                if column in covered:
                    continue
                found.append(
                    Finding(
                        MIGRATIONS_FILE,
                        1,
                        f"{table}.{column} points at {key['table']} with no index behind it",
                    )
                )
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("check_indexes", findings())


if __name__ == "__main__":
    sys.exit(main())
