"""Reading and writing the chromatography readings."""

from __future__ import annotations

import sqlite3

from molycow.errors import NotFoundError
from molycow.model.purity import PurityTest, Strip, System
from molycow.store.book import Book
from molycow.store.rows import moment_in, moment_out, text_in


def purity_from(row: sqlite3.Row) -> PurityTest:
    return PurityTest(
        batch_id=text_in(row, "batch_id"),
        tested_at=moment_in(row["tested_at"], "tested_at"),
        solvent=Strip(
            System.SOLVENT,
            origin=int(row["solvent_origin"]),
            front=int(row["solvent_front"]),
            background=int(row["solvent_background"]),
        ),
        saline=Strip(
            System.SALINE,
            origin=int(row["saline_origin"]),
            front=int(row["saline_front"]),
            background=int(row["saline_background"]),
        ),
        tested_by=text_in(row, "tested_by"),
    )


class PurityRepository:
    """One reading per batch."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, reading: PurityTest) -> PurityTest:
        self._book.execute(
            """
            INSERT INTO purity_test
              (batch_id, tested_at, solvent_origin, solvent_front, solvent_background,
               saline_origin, saline_front, saline_background, tested_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading.batch_id,
                moment_out(reading.tested_at),
                reading.solvent.origin,
                reading.solvent.front,
                reading.solvent.background,
                reading.saline.origin,
                reading.saline.front,
                reading.saline.background,
                reading.tested_by,
            ),
        )
        return reading

    def find(self, batch_id: str) -> PurityTest | None:
        row = self._book.one("SELECT * FROM purity_test WHERE batch_id = ?", (batch_id,))
        return None if row is None else purity_from(row)

    def get(self, batch_id: str) -> PurityTest:
        found = self.find(batch_id)
        if found is None:
            raise NotFoundError("that batch has no purity reading", batch=batch_id)
        return found

    def all(self) -> list[PurityTest]:
        rows = self._book.all("SELECT * FROM purity_test ORDER BY tested_at, batch_id")
        return [purity_from(row) for row in rows]
