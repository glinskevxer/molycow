"""Reading and writing the eluate tests."""

from __future__ import annotations

import sqlite3

from molycow.errors import NotFoundError
from molycow.model.breakthrough import Breakthrough
from molycow.store.book import Book
from molycow.store.rows import (
    activity_in,
    activity_out,
    decimal_in,
    decimal_out,
    moment_in,
    moment_out,
    text_in,
)


def breakthrough_from(row: sqlite3.Row) -> Breakthrough:
    """Build a breakthrough out of a row of the table."""
    return Breakthrough(
        elution_id=text_in(row, "elution_id"),
        tested_at=moment_in(row["tested_at"], "tested_at"),
        moly=activity_in(row["moly"], "moly"),
        technetium=activity_in(row["technetium"], "technetium"),
        aluminium_ppm=decimal_in(row["aluminium_ppm"], "aluminium_ppm"),
        tested_by=text_in(row, "tested_by"),
    )


class BreakthroughRepository:
    """One test per elution, and it does not get run twice."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, test: Breakthrough) -> Breakthrough:
        self._book.execute(
            """
            INSERT INTO breakthrough
              (elution_id, tested_at, moly, technetium, aluminium_ppm, tested_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                test.elution_id,
                moment_out(test.tested_at),
                activity_out(test.moly),
                activity_out(test.technetium),
                decimal_out(test.aluminium_ppm),
                test.tested_by,
            ),
        )
        return test

    def find(self, elution_id: str) -> Breakthrough | None:
        row = self._book.one("SELECT * FROM breakthrough WHERE elution_id = ?", (elution_id,))
        return None if row is None else breakthrough_from(row)

    def get(self, elution_id: str) -> Breakthrough:
        """One breakthrough test, or a refusal if it is not in the book."""
        found = self.find(elution_id)
        if found is None:
            raise NotFoundError("that eluate has not been tested", elution=elution_id)
        return found

    def all(self) -> list[Breakthrough]:
        rows = self._book.all("SELECT * FROM breakthrough ORDER BY tested_at, elution_id")
        return [breakthrough_from(row) for row in rows]

    def failures(self) -> list[Breakthrough]:
        return [one for one in self.all() if not one.passes]
