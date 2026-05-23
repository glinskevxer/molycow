"""Reading and writing the audit trail."""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.model.audit import Entry
from molycow.store.records import Records
from molycow.store.rows import moment_in, moment_out, text_in


def entry_from(row: sqlite3.Row) -> Entry:
    """Build an entry out of a row of the table."""
    return Entry(
        at=moment_in(row["done_at"], "done_at"),
        actor=text_in(row, "actor"),
        action=text_in(row, "action"),
        subject=text_in(row, "subject"),
        detail=text_in(row, "detail"),
    )


class AuditRepository(Records):
    """Everything that has been done to the book, in the order it happened."""

    def add(self, entry: Entry) -> Entry:
        self._book.execute(
            """
            INSERT INTO audit (done_at, actor, action, subject, detail)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                moment_out(entry.at),
                entry.actor,
                entry.action,
                entry.subject,
                entry.detail,
            ),
        )
        return entry

    def record(
        self, at: dt.datetime, actor: str, action: str, subject: str, detail: str = ""
    ) -> Entry:
        """Write one line without the caller having to build it."""
        return self.add(Entry(at=at, actor=actor, action=action, subject=subject, detail=detail))

    def all(self) -> list[Entry]:
        rows = self._book.all("SELECT * FROM audit ORDER BY done_at, id")
        return [entry_from(row) for row in rows]

    def for_subject(self, subject: str) -> list[Entry]:
        """Every line about one record."""
        rows = self._book.all(
            "SELECT * FROM audit WHERE subject = ? ORDER BY done_at, id", (subject,)
        )
        return [entry_from(row) for row in rows]

    def by_actor(self, actor: str) -> list[Entry]:
        """Every line one person left."""
        rows = self._book.all("SELECT * FROM audit WHERE actor = ? ORDER BY done_at, id", (actor,))
        return [entry_from(row) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Entry]:
        """Every line from one local day."""
        where = tz or zone()
        return [one for one in self.all() if day_of(one.at, where) == day]

    def count(self) -> int:
        return int(self._book.value("SELECT count(*) FROM audit") or 0)
