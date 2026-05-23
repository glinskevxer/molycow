"""Reading and writing the fridge log."""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.model.fridge import FridgeReading
from molycow.store.records import Records
from molycow.store.rows import (
    decimal_in,
    decimal_out,
    maybe_moment_in,
    maybe_text_in,
    moment_in,
    moment_out,
    text_in,
)


def reading_from(row: sqlite3.Row) -> FridgeReading:
    """Build a fridge reading out of a row of the table."""
    return FridgeReading(
        read_at=moment_in(row["read_at"], "read_at"),
        celsius=decimal_in(row["celsius"], "celsius"),
        read_by=text_in(row, "read_by"),
        reviewed_at=maybe_moment_in(row["reviewed_at"], "reviewed_at"),
        reviewed_by=maybe_text_in(row, "reviewed_by"),
    )


class FridgeRepository(Records):
    """Every reading taken off the fridge."""

    def add(self, reading: FridgeReading) -> FridgeReading:
        self._book.execute(
            "INSERT INTO fridge_reading (read_at, celsius, read_by) VALUES (?, ?, ?)",
            (moment_out(reading.read_at), decimal_out(reading.celsius), reading.read_by),
        )
        return reading

    def all(self) -> list[FridgeReading]:
        rows = self._book.all("SELECT * FROM fridge_reading ORDER BY read_at, id")
        return [reading_from(row) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[FridgeReading]:
        """Every reading taken on one local day."""
        where = tz or zone()
        return [one for one in self.all() if day_of(one.read_at, where) == day]

    def excursions(self) -> list[FridgeReading]:
        """Every reading outside the range, reviewed or not."""
        return [one for one in self.all() if one.is_excursion]

    def open_excursions(self) -> list[FridgeReading]:
        """Excursions nobody has looked at."""
        return [one for one in self.all() if one.is_open]

    def review(self, read_at: dt.datetime, at: dt.datetime, by: str) -> FridgeReading:
        """Put a name against one excursion."""
        row = self._book.one(
            "SELECT * FROM fridge_reading WHERE read_at = ?", (moment_out(read_at),)
        )
        found = self.required(
            None if row is None else reading_from(row),
            "no reading was taken at that moment",
            read_at=read_at.isoformat(),
        )
        reviewed = found.reviewed(at, by)
        self._book.execute(
            "UPDATE fridge_reading SET reviewed_at = ?, reviewed_by = ? WHERE read_at = ?",
            (moment_out(at), by, moment_out(read_at)),
        )
        return reviewed

    def latest(self) -> FridgeReading | None:
        """The last reading taken, if there is one."""
        found = self.all()
        return found[-1] if found else None
