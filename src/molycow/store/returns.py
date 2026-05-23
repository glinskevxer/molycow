"""Reading and writing the returns."""

from __future__ import annotations

import sqlite3

from molycow.model.dose import DoseReturn
from molycow.store.records import Records
from molycow.store.rows import maybe_text_in, moment_in, moment_out, text_in


def return_from(row: sqlite3.Row) -> DoseReturn:
    """Build a return out of a row of the table."""
    return DoseReturn(
        dose_id=text_in(row, "dose_id"),
        returned_at=moment_in(row["returned_at"], "returned_at"),
        reason=text_in(row, "reason"),
        received_by=text_in(row, "received_by"),
        container_id=maybe_text_in(row, "container_id"),
    )


class ReturnRepository(Records):
    """Every syringe that came back."""

    def add(self, came_back: DoseReturn) -> DoseReturn:
        self._book.execute(
            """
            INSERT INTO dose_return (dose_id, returned_at, reason, received_by, container_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                came_back.dose_id,
                moment_out(came_back.returned_at),
                came_back.reason,
                came_back.received_by,
                came_back.container_id,
            ),
        )
        return came_back

    def find(self, dose_id: str) -> DoseReturn | None:
        row = self._book.one("SELECT * FROM dose_return WHERE dose_id = ?", (dose_id,))
        return None if row is None else return_from(row)

    def get(self, dose_id: str) -> DoseReturn:
        """One return, or a refusal if that syringe is still out."""
        return self.required(self.find(dose_id), "that dose has not come back", dose=dose_id)

    def all(self) -> list[DoseReturn]:
        rows = self._book.all("SELECT * FROM dose_return ORDER BY returned_at, dose_id")
        return [return_from(row) for row in rows]

    def count(self) -> int:
        return int(self._book.value("SELECT count(*) FROM dose_return") or 0)
