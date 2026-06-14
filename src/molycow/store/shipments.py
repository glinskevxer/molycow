"""Reading and writing the shipping log."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.ids import Kind
from molycow.model.shipment import Shipment
from molycow.store.records import Records
from molycow.store.rows import (
    activity_in,
    activity_out,
    decimal_in,
    decimal_out,
    maybe_moment_in,
    maybe_text_in,
    moment_in,
    moment_out,
    text_in,
)
from molycow.store.serials import next_id


class ShipmentRepository(Records):
    """Every box that has gone out."""

    def add(self, shipment: Shipment) -> Shipment:
        with self._book.atomic():
            self._book.execute(
                """
                INSERT INTO shipment
                  (id, customer_id, packed_at, packed_by, symbol, activity,
                   surface_mrem, metre_mrem, delivered_at, received_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shipment.id,
                    shipment.customer_id,
                    moment_out(shipment.packed_at),
                    shipment.packed_by,
                    shipment.symbol,
                    activity_out(shipment.activity),
                    decimal_out(shipment.surface_mrem),
                    decimal_out(shipment.metre_mrem),
                    None if shipment.delivered_at is None else moment_out(shipment.delivered_at),
                    shipment.received_by,
                ),
            )
            self._book.execute_many(
                "INSERT INTO shipment_dose (shipment_id, dose_id) VALUES (?, ?)",
                [(shipment.id, dose_id) for dose_id in shipment.dose_ids],
            )
        return shipment

    def find(self, shipment_id: str) -> Shipment | None:
        row = self._book.one("SELECT * FROM shipment WHERE id = ?", (shipment_id,))
        if row is None:
            return None
        doses = self._book.all(
            "SELECT dose_id FROM shipment_dose WHERE shipment_id = ? ORDER BY dose_id",
            (shipment_id,),
        )
        return Shipment(
            id=text_in(row, "id"),
            customer_id=text_in(row, "customer_id"),
            packed_at=moment_in(row["packed_at"], "packed_at"),
            packed_by=text_in(row, "packed_by"),
            dose_ids=tuple(str(one["dose_id"]) for one in doses),
            symbol=text_in(row, "symbol"),
            activity=activity_in(row["activity"], "activity"),
            surface_mrem=decimal_in(row["surface_mrem"], "surface_mrem"),
            metre_mrem=decimal_in(row["metre_mrem"], "metre_mrem"),
            delivered_at=maybe_moment_in(row["delivered_at"], "delivered_at"),
            received_by=maybe_text_in(row, "received_by"),
        )

    def get(self, shipment_id: str) -> Shipment:
        """One shipment, or a refusal if it is not in the book."""
        return self.required(self.find(shipment_id), "no such shipment", id=shipment_id)

    def all(self) -> list[Shipment]:
        rows = self._book.all("SELECT id FROM shipment ORDER BY packed_at, id")
        return [self.get(str(row["id"])) for row in rows]

    def for_customer(self, customer_id: str) -> list[Shipment]:
        rows = self._book.all(
            "SELECT id FROM shipment WHERE customer_id = ? ORDER BY packed_at, id",
            (customer_id,),
        )
        return [self.get(str(row["id"])) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Shipment]:
        where = tz or zone()
        return [one for one in self.all() if day_of(one.packed_at, where) == day]

    def holding(self, dose_id: str) -> Shipment | None:
        row = self._book.one("SELECT shipment_id FROM shipment_dose WHERE dose_id = ?", (dose_id,))
        return None if row is None else self.get(str(row["shipment_id"]))

    def undelivered(self) -> list[Shipment]:
        return [one for one in self.all() if not one.is_delivered]

    def sign_for(self, shipment_id: str, at: dt.datetime, received_by: str) -> Shipment:
        signed = self.get(shipment_id).delivered(at, received_by)
        self._book.execute(
            "UPDATE shipment SET delivered_at = ?, received_by = ? WHERE id = ?",
            (moment_out(at), received_by, shipment_id),
        )
        return signed

    def next_id(self, day: dt.date) -> str:
        return next_id(self._book, Kind.SHIPMENT, day)
