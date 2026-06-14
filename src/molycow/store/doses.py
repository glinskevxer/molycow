"""Reading and writing the dispensing log."""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.ids import Kind
from molycow.model.dose import Dose
from molycow.store.records import Records
from molycow.store.rows import (
    activity_in,
    activity_out,
    maybe_text_in,
    moment_in,
    moment_out,
    text_in,
    volume_in,
    volume_out,
)
from molycow.store.serials import next_id


def dose_from(row: sqlite3.Row) -> Dose:
    """Build a dose out of a row of the table."""
    return Dose(
        id=text_in(row, "id"),
        order_id=text_in(row, "order_id"),
        batch_id=text_in(row, "batch_id"),
        code=text_in(row, "code"),
        drawn_at=moment_in(row["drawn_at"], "drawn_at"),
        calibration_at=moment_in(row["calibration_at"], "calibration_at"),
        volume=volume_in(row["volume"], "volume"),
        assayed=activity_in(row["assayed"], "assayed"),
        drawn_by=text_in(row, "drawn_by"),
        calibrator_id=maybe_text_in(row, "calibrator_id"),
    )


class DoseRepository(Records):
    """Every syringe that has been drawn."""

    def add(self, dose: Dose) -> Dose:
        self._book.execute(
            """
            INSERT INTO dose
              (id, order_id, batch_id, code, drawn_at, calibration_at,
               volume, assayed, drawn_by, calibrator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dose.id,
                dose.order_id,
                dose.batch_id,
                dose.code,
                moment_out(dose.drawn_at),
                moment_out(dose.calibration_at),
                volume_out(dose.volume),
                activity_out(dose.assayed),
                dose.drawn_by,
                dose.calibrator_id,
            ),
        )
        return dose

    def find(self, dose_id: str) -> Dose | None:
        row = self._book.one("SELECT * FROM dose WHERE id = ?", (dose_id,))
        return None if row is None else dose_from(row)

    def get(self, dose_id: str) -> Dose:
        """One dose, or a refusal if it is not in the book."""
        return self.required(self.find(dose_id), "no such dose", id=dose_id)

    def all(self) -> list[Dose]:
        rows = self._book.all("SELECT * FROM dose ORDER BY drawn_at, id")
        return [dose_from(row) for row in rows]

    def for_order(self, order_id: str) -> Dose | None:
        row = self._book.one("SELECT * FROM dose WHERE order_id = ?", (order_id,))
        return None if row is None else dose_from(row)

    def for_batch(self, batch_id: str) -> list[Dose]:
        rows = self._book.all(
            "SELECT * FROM dose WHERE batch_id = ? ORDER BY drawn_at, id", (batch_id,)
        )
        return [dose_from(row) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Dose]:
        where = tz or zone()
        return [one for one in self.all() if day_of(one.drawn_at, where) == day]

    def next_id(self, day: dt.date) -> str:
        return next_id(self._book, Kind.DOSE, day)

    def count_on(self, day: dt.date, tz: ZoneInfo | None = None) -> int:
        return len(self.on_day(day, tz))
