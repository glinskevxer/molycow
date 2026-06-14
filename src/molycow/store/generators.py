"""Reading and writing the generator bench."""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.ids import Kind
from molycow.model.generator import Elution, Generator
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
    volume_in,
    volume_out,
)
from molycow.store.serials import next_id


def generator_from(row: sqlite3.Row) -> Generator:
    """Build a generator out of a row of the table."""
    return Generator(
        id=text_in(row, "id"),
        serial=text_in(row, "serial"),
        maker=text_in(row, "maker"),
        calibrated_at=moment_in(row["calibrated_at"], "calibrated_at"),
        calibrated_activity=activity_in(row["calibrated_activity"], "calibrated_activity"),
        received_on=date_in(row["received_on"], "received_on"),
        expires_on=date_in(row["expires_on"], "expires_on"),
        retired_on=maybe_date_in(row["retired_on"], "retired_on"),
    )


def elution_from(row: sqlite3.Row) -> Elution:
    """Build a elution out of a row of the table."""
    return Elution(
        id=text_in(row, "id"),
        generator_id=text_in(row, "generator_id"),
        drawn_at=moment_in(row["drawn_at"], "drawn_at"),
        volume=volume_in(row["volume"], "volume"),
        activity=activity_in(row["activity"], "activity"),
        expected=activity_in(row["expected"], "expected"),
        residual=activity_in(row["residual"], "residual"),
    )


class GeneratorRepository(Records):
    """Every column the pharmacy has had."""

    def add(self, generator: Generator) -> Generator:
        self._book.execute(
            """
            INSERT INTO generator
              (id, serial, maker, calibrated_at, calibrated_activity,
               received_on, expires_on, retired_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generator.id,
                generator.serial,
                generator.maker,
                moment_out(generator.calibrated_at),
                activity_out(generator.calibrated_activity),
                date_out(generator.received_on),
                date_out(generator.expires_on),
                date_out(generator.retired_on),
            ),
        )
        return generator

    def find(self, generator_id: str) -> Generator | None:
        row = self._book.one("SELECT * FROM generator WHERE id = ?", (generator_id,))
        return None if row is None else generator_from(row)

    def get(self, generator_id: str) -> Generator:
        """One column, or a refusal if it is not in the book."""
        return self.required(self.find(generator_id), "no such generator", id=generator_id)

    def all(self) -> list[Generator]:
        return [
            generator_from(row) for row in self._book.all("SELECT * FROM generator ORDER BY id")
        ]

    def in_date_on(self, day: dt.date) -> list[Generator]:
        """The columns that may be milked on a day, oldest first."""
        found = [one for one in self.all() if one.is_in_date(day)]
        return sorted(found, key=lambda one: (one.received_on, one.id))

    def retire(self, generator_id: str, on: dt.date) -> Generator:
        current = self.get(generator_id)
        self._book.execute(
            "UPDATE generator SET retired_on = ? WHERE id = ?",
            (date_out(on), generator_id),
        )
        return Generator(
            id=current.id,
            serial=current.serial,
            maker=current.maker,
            calibrated_at=current.calibrated_at,
            calibrated_activity=current.calibrated_activity,
            received_on=current.received_on,
            expires_on=current.expires_on,
            retired_on=on,
        )

    def next_id(self) -> str:
        return next_id(self._book, Kind.GENERATOR)


class ElutionRepository(Records):
    """Every milking, in the order it happened."""

    def add(self, elution: Elution) -> Elution:
        self._book.execute(
            """
            INSERT INTO elution
              (id, generator_id, drawn_at, volume, activity, expected, residual)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                elution.id,
                elution.generator_id,
                moment_out(elution.drawn_at),
                volume_out(elution.volume),
                activity_out(elution.activity),
                activity_out(elution.expected),
                activity_out(elution.residual),
            ),
        )
        return elution

    def find(self, elution_id: str) -> Elution | None:
        row = self._book.one("SELECT * FROM elution WHERE id = ?", (elution_id,))
        return None if row is None else elution_from(row)

    def get(self, elution_id: str) -> Elution:
        """One elution, or a refusal if it is not in the book."""
        return self.required(self.find(elution_id), "no such elution", id=elution_id)

    def for_generator(self, generator_id: str) -> list[Elution]:
        rows = self._book.all(
            "SELECT * FROM elution WHERE generator_id = ? ORDER BY drawn_at, id",
            (generator_id,),
        )
        return [elution_from(row) for row in rows]

    def last_for(self, generator_id: str) -> Elution | None:
        row = self._book.one(
            "SELECT * FROM elution WHERE generator_id = ? ORDER BY drawn_at DESC, id DESC LIMIT 1",
            (generator_id,),
        )
        return None if row is None else elution_from(row)

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Elution]:
        """Every elution whose local day is the one asked for."""
        where = tz if tz is not None else zone()
        return [one for one in self.all() if day_of(one.drawn_at, where) == day]

    def all(self) -> list[Elution]:
        rows = self._book.all("SELECT * FROM elution ORDER BY drawn_at, id")
        return [elution_from(row) for row in rows]

    def next_id(self, day: dt.date) -> str:
        """The next elution number for a day, which restarts every morning."""
        return next_id(self._book, Kind.ELUTION, day)

    def count_for(self, generator_id: str) -> int:
        value = self._book.value(
            "SELECT count(*) FROM elution WHERE generator_id = ?", (generator_id,)
        )
        return int(value or 0)
