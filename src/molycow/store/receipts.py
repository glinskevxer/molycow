"""Reading and writing the receiving log."""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.model.receipt import PackageReceipt
from molycow.store.records import Records
from molycow.store.rows import decimal_in, decimal_out, moment_in, moment_out, text_in


def receipt_from(row: sqlite3.Row) -> PackageReceipt:
    """Build a package receipt out of a row of the table."""
    return PackageReceipt(
        reference=text_in(row, "reference"),
        supplier=text_in(row, "supplier"),
        received_at=moment_in(row["received_at"], "received_at"),
        surface_mrem=decimal_in(row["surface_mrem"], "surface_mrem"),
        metre_mrem=decimal_in(row["metre_mrem"], "metre_mrem"),
        wipe_dpm=decimal_in(row["wipe_dpm"], "wipe_dpm"),
        received_by=text_in(row, "received_by"),
    )


class ReceiptRepository(Records):
    """Every package the dock has booked in."""

    def add(self, receipt: PackageReceipt) -> PackageReceipt:
        self._book.execute(
            """
            INSERT INTO package_receipt
              (reference, supplier, received_at, surface_mrem, metre_mrem, wipe_dpm, received_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.reference,
                receipt.supplier,
                moment_out(receipt.received_at),
                decimal_out(receipt.surface_mrem),
                decimal_out(receipt.metre_mrem),
                decimal_out(receipt.wipe_dpm),
                receipt.received_by,
            ),
        )
        return receipt

    def find(self, reference: str) -> PackageReceipt | None:
        row = self._book.one("SELECT * FROM package_receipt WHERE reference = ?", (reference,))
        return None if row is None else receipt_from(row)

    def get(self, reference: str) -> PackageReceipt:
        """One receipt, or a refusal if that package was never booked in."""
        return self.required(
            self.find(reference), "no package with that reference", reference=reference
        )

    def all(self) -> list[PackageReceipt]:
        rows = self._book.all("SELECT * FROM package_receipt ORDER BY received_at, reference")
        return [receipt_from(row) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[PackageReceipt]:
        """Every package booked in on one local day."""
        where = tz or zone()
        return [one for one in self.all() if day_of(one.received_at, where) == day]

    def failures(self) -> list[PackageReceipt]:
        """Every package that did not pass on arrival."""
        return [one for one in self.all() if not one.passes]

    def link_generator(self, generator_id: str, reference: str) -> None:
        """Say which package a column came out of."""
        self._book.execute(
            "UPDATE generator SET package_reference = ? WHERE id = ?",
            (reference, generator_id),
        )

    def package_of(self, generator_id: str) -> str | None:
        """The package a column came out of, if it was recorded."""
        row = self._book.one(
            "SELECT package_reference FROM generator WHERE id = ?", (generator_id,)
        )
        if row is None or row["package_reference"] is None:
            return None
        return str(row["package_reference"])
