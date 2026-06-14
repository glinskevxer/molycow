"""Reading and writing the instruments, their sources and their checks."""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import NotFoundError
from molycow.ids import Kind
from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
from molycow.model.qc import CheckKind, LinearityPoint, LinearityRun, QcCheck
from molycow.store.records import Records
from molycow.store.rows import (
    activity_in,
    activity_out,
    date_in,
    date_out,
    maybe_date_in,
    moment_in,
    moment_out,
    text_in,
)
from molycow.store.serials import next_id


def instrument_from(row: sqlite3.Row) -> Instrument:
    """Build a instrument out of a row of the table."""
    return Instrument(
        id=text_in(row, "id"),
        kind=InstrumentKind(text_in(row, "kind")),
        maker=text_in(row, "maker"),
        model=text_in(row, "model"),
        serial=text_in(row, "serial"),
        installed_on=date_in(row["installed_on"], "installed_on"),
        calibrated_on=date_in(row["calibrated_on"], "calibrated_on"),
        retired_on=maybe_date_in(row["retired_on"], "retired_on"),
    )


def source_from(row: sqlite3.Row) -> CheckSource:
    """Build a source out of a row of the table."""
    return CheckSource(
        serial=text_in(row, "serial"),
        symbol=text_in(row, "symbol"),
        certified_activity=activity_in(row["certified_activity"], "certified_activity"),
        certified_on=date_in(row["certified_on"], "certified_on"),
        retired_on=maybe_date_in(row["retired_on"], "retired_on"),
    )


def check_from(row: sqlite3.Row) -> QcCheck:
    """Build a check out of a row of the table."""
    return QcCheck(
        instrument_id=text_in(row, "instrument_id"),
        kind=CheckKind(text_in(row, "kind")),
        at=moment_in(row["ran_at"], "ran_at"),
        source_serial=text_in(row, "source_serial"),
        expected=activity_in(row["expected"], "expected"),
        measured=activity_in(row["measured"], "measured"),
        checked_by=text_in(row, "checked_by"),
    )


class InstrumentRepository(Records):
    """The instruments in the lab."""

    def add(self, instrument: Instrument) -> Instrument:
        self._book.execute(
            """
            INSERT INTO instrument
              (id, kind, maker, model, serial, installed_on, calibrated_on, retired_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instrument.id,
                instrument.kind.value,
                instrument.maker,
                instrument.model,
                instrument.serial,
                date_out(instrument.installed_on),
                date_out(instrument.calibrated_on),
                date_out(instrument.retired_on),
            ),
        )
        return instrument

    def find(self, instrument_id: str) -> Instrument | None:
        row = self._book.one("SELECT * FROM instrument WHERE id = ?", (instrument_id,))
        return None if row is None else instrument_from(row)

    def get(self, instrument_id: str) -> Instrument:
        """One instrument, or a refusal if it is not in the book."""
        return self.required(self.find(instrument_id), "no such instrument", id=instrument_id)

    def all(self) -> list[Instrument]:
        rows = self._book.all("SELECT * FROM instrument ORDER BY id")
        return [instrument_from(row) for row in rows]

    def of_kind(self, kind: InstrumentKind, usable_on: dt.date | None = None) -> list[Instrument]:
        found = [one for one in self.all() if one.kind is kind]
        if usable_on is not None:
            found = [one for one in found if one.is_usable_on(usable_on)]
        return found

    def recalibrate(self, instrument_id: str, on: dt.date) -> Instrument:
        current = self.get(instrument_id)
        self._book.execute(
            "UPDATE instrument SET calibrated_on = ? WHERE id = ?", (date_out(on), instrument_id)
        )
        return Instrument(
            id=current.id,
            kind=current.kind,
            maker=current.maker,
            model=current.model,
            serial=current.serial,
            installed_on=current.installed_on,
            calibrated_on=on,
            retired_on=current.retired_on,
        )

    def next_id(self) -> str:
        return next_id(self._book, Kind.INSTRUMENT)


class CheckSourceRepository(Records):
    """The sealed sources on the shelf."""

    def add(self, source: CheckSource) -> CheckSource:
        self._book.execute(
            """
            INSERT INTO check_source
              (serial, symbol, certified_activity, certified_on, retired_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                source.serial,
                source.symbol,
                activity_out(source.certified_activity),
                date_out(source.certified_on),
                date_out(source.retired_on),
            ),
        )
        return source

    def find(self, serial: str) -> CheckSource | None:
        row = self._book.one("SELECT * FROM check_source WHERE serial = ?", (serial,))
        return None if row is None else source_from(row)

    def get(self, serial: str) -> CheckSource:
        """One check source, or a refusal if it is not in the book."""
        return self.required(self.find(serial), "no such check source", serial=serial)

    def all(self) -> list[CheckSource]:
        rows = self._book.all("SELECT * FROM check_source ORDER BY serial")
        return [source_from(row) for row in rows]

    def in_use_on(self, day: dt.date) -> list[CheckSource]:
        return [one for one in self.all() if one.is_in_use_on(day)]


class QcRepository(Records):
    """Every check that has been run, and the linearity runs."""

    def add(self, check: QcCheck) -> QcCheck:
        self._book.execute(
            """
            INSERT INTO qc_check
              (instrument_id, kind, ran_at, source_serial, expected, measured, checked_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                check.instrument_id,
                check.kind.value,
                moment_out(check.at),
                check.source_serial,
                activity_out(check.expected),
                activity_out(check.measured),
                check.checked_by,
            ),
        )
        return check

    def all(self) -> list[QcCheck]:
        rows = self._book.all("SELECT * FROM qc_check ORDER BY ran_at, instrument_id")
        return [check_from(row) for row in rows]

    def for_instrument(self, instrument_id: str, kind: CheckKind | None = None) -> list[QcCheck]:
        rows = self._book.all(
            "SELECT * FROM qc_check WHERE instrument_id = ? ORDER BY ran_at",
            (instrument_id,),
        )
        found = [check_from(row) for row in rows]
        if kind is not None:
            found = [one for one in found if one.kind is kind]
        return found

    def on_day(
        self, instrument_id: str, kind: CheckKind, day: dt.date, tz: ZoneInfo | None = None
    ) -> list[QcCheck]:
        where = tz or zone()
        return [
            one for one in self.for_instrument(instrument_id, kind) if day_of(one.at, where) == day
        ]

    def last(self, instrument_id: str, kind: CheckKind) -> QcCheck | None:
        found = self.for_instrument(instrument_id, kind)
        return found[-1] if found else None

    def add_run(self, run: LinearityRun) -> int:
        """Write a linearity run and its readings, and give back its number."""
        with self._book.atomic():
            cursor = self._book.execute(
                "INSERT INTO linearity_run (instrument_id, symbol, checked_by) VALUES (?, ?, ?)",
                (run.instrument_id, run.symbol, run.checked_by),
            )
            run_id = int(cursor.lastrowid or 0)
            self._book.execute_many(
                "INSERT INTO linearity_point (run_id, read_at, measured) VALUES (?, ?, ?)",
                [
                    (run_id, moment_out(point.at), activity_out(point.measured))
                    for point in run.points
                ],
            )
        return run_id

    def get_run(self, run_id: int) -> LinearityRun:
        """One linearity run and its readings, or a refusal."""
        row = self._book.one("SELECT * FROM linearity_run WHERE id = ?", (run_id,))
        if row is None:
            raise NotFoundError("no such linearity run", run=run_id)
        points = self._book.all(
            "SELECT * FROM linearity_point WHERE run_id = ? ORDER BY read_at", (run_id,)
        )
        return LinearityRun(
            instrument_id=text_in(row, "instrument_id"),
            symbol=text_in(row, "symbol"),
            points=tuple(
                LinearityPoint(
                    at=moment_in(point["read_at"], "read_at"),
                    measured=activity_in(point["measured"], "measured"),
                )
                for point in points
            ),
            checked_by=text_in(row, "checked_by"),
        )

    def runs_for(self, instrument_id: str) -> list[int]:
        rows = self._book.all(
            "SELECT id FROM linearity_run WHERE instrument_id = ? ORDER BY id", (instrument_id,)
        )
        return [int(row["id"]) for row in rows]
