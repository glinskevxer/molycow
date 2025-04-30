"""Reading and writing the kit shelf and the compounded batches."""

from __future__ import annotations

import datetime as dt
import sqlite3
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import NotFoundError
from molycow.ids import Kind, make, next_serial
from molycow.model.kit import Batch, KitLot
from molycow.store.book import Book
from molycow.store.rows import (
    activity_in,
    activity_out,
    date_in,
    date_out,
    decimal_in,
    decimal_out,
    moment_in,
    moment_out,
    text_in,
    volume_in,
    volume_out,
)


def kit_lot_from(row: sqlite3.Row) -> KitLot:
    return KitLot(
        id=text_in(row, "id"),
        code=text_in(row, "code"),
        maker=text_in(row, "maker"),
        lot=text_in(row, "lot"),
        received_on=date_in(row["received_on"], "received_on"),
        expires_on=date_in(row["expires_on"], "expires_on"),
        vials=int(row["vials"]),
    )


def batch_from(row: sqlite3.Row) -> Batch:
    rcp = row["rcp"]
    return Batch(
        id=text_in(row, "id"),
        kit_lot_id=text_in(row, "kit_lot_id"),
        elution_id=text_in(row, "elution_id"),
        code=text_in(row, "code"),
        made_at=moment_in(row["made_at"], "made_at"),
        activity=activity_in(row["activity"], "activity"),
        volume=volume_in(row["volume"], "volume"),
        made_by=text_in(row, "made_by"),
        rcp=None if rcp is None else decimal_in(rcp, "rcp"),
    )


class KitLotRepository:
    """The cold kits on the shelf."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, lot: KitLot) -> KitLot:
        self._book.execute(
            """
            INSERT INTO kit_lot (id, code, maker, lot, received_on, expires_on, vials)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lot.id,
                lot.code,
                lot.maker,
                lot.lot,
                date_out(lot.received_on),
                date_out(lot.expires_on),
                lot.vials,
            ),
        )
        return lot

    def find(self, lot_id: str) -> KitLot | None:
        row = self._book.one("SELECT * FROM kit_lot WHERE id = ?", (lot_id,))
        return None if row is None else kit_lot_from(row)

    def get(self, lot_id: str) -> KitLot:
        found = self.find(lot_id)
        if found is None:
            raise NotFoundError("no such kit lot", id=lot_id)
        return found

    def all(self) -> list[KitLot]:
        return [kit_lot_from(row) for row in self._book.all("SELECT * FROM kit_lot ORDER BY id")]

    def for_code(self, code: str, in_date_on: dt.date | None = None) -> list[KitLot]:
        """The lots of one kit, the ones expiring first at the front."""
        rows = self._book.all(
            "SELECT * FROM kit_lot WHERE code = ? ORDER BY expires_on, id",
            (code.strip().upper(),),
        )
        found = [kit_lot_from(row) for row in rows]
        if in_date_on is not None:
            found = [one for one in found if one.is_in_date(in_date_on)]
        return found

    def oldest_in_date(self, code: str, on: dt.date) -> KitLot | None:
        """The lot the bench should reach for, which is the one nearest expiry."""
        lots = self.for_code(code, in_date_on=on)
        return lots[0] if lots else None

    def next_id(self) -> str:
        issued = [str(row["id"]) for row in self._book.all("SELECT id FROM kit_lot")]
        return make(Kind.KIT_LOT, next_serial(issued, Kind.KIT_LOT))

    def count(self) -> int:
        return int(self._book.value("SELECT count(*) FROM kit_lot") or 0)


class BatchRepository:
    """Everything compounded on the bench."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, batch: Batch) -> Batch:
        self._book.execute(
            """
            INSERT INTO batch
              (id, kit_lot_id, elution_id, code, made_at, activity, volume, made_by, rcp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.id,
                batch.kit_lot_id,
                batch.elution_id,
                batch.code,
                moment_out(batch.made_at),
                activity_out(batch.activity),
                volume_out(batch.volume),
                batch.made_by,
                None if batch.rcp is None else decimal_out(batch.rcp),
            ),
        )
        return batch

    def find(self, batch_id: str) -> Batch | None:
        row = self._book.one("SELECT * FROM batch WHERE id = ?", (batch_id,))
        return None if row is None else batch_from(row)

    def get(self, batch_id: str) -> Batch:
        found = self.find(batch_id)
        if found is None:
            raise NotFoundError("no such batch", id=batch_id)
        return found

    def all(self) -> list[Batch]:
        rows = self._book.all("SELECT * FROM batch ORDER BY made_at, id")
        return [batch_from(row) for row in rows]

    def for_elution(self, elution_id: str) -> list[Batch]:
        rows = self._book.all(
            "SELECT * FROM batch WHERE elution_id = ? ORDER BY made_at, id", (elution_id,)
        )
        return [batch_from(row) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Batch]:
        where = tz or zone()
        return [one for one in self.all() if day_of(one.made_at, where) == day]

    def in_date_at(self, moment: dt.datetime, code: str | None = None) -> list[Batch]:
        found = [one for one in self.all() if one.is_in_date_at(moment)]
        if code is not None:
            wanted = code.strip().upper()
            found = [one for one in found if one.code == wanted]
        return found

    def record_purity(self, batch_id: str, rcp: Decimal) -> Batch:
        tested = self.get(batch_id).with_purity(rcp)
        self._book.execute("UPDATE batch SET rcp = ? WHERE id = ?", (decimal_out(rcp), batch_id))
        return tested

    def untested(self) -> list[Batch]:
        return [one for one in self.all() if not one.is_tested]

    def next_id(self, day: dt.date) -> str:
        issued = [str(row["id"]) for row in self._book.all("SELECT id FROM batch")]
        return make(Kind.BATCH, next_serial(issued, Kind.BATCH, day), day)
