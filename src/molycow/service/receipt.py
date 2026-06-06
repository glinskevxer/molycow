"""Booking a package in, and refusing to open one that failed its survey."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import ConflictError, SafetyError
from molycow.model.receipt import PackageReceipt
from molycow.store.book import Book
from molycow.store.receipts import ReceiptRepository


class ReceiptService:
    """The receiving dock."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._receipts = ReceiptRepository(book)

    def receive(
        self,
        reference: str,
        supplier: str,
        at: dt.datetime,
        surface_mrem: Decimal,
        metre_mrem: Decimal,
        wipe_dpm: Decimal,
        received_by: str,
    ) -> PackageReceipt:
        """Book a package in with the readings taken on it."""
        if self._receipts.find(reference) is not None:
            raise ConflictError("that package is already booked in", reference=reference)
        receipt = PackageReceipt(
            reference=reference,
            supplier=supplier,
            received_at=at,
            surface_mrem=surface_mrem,
            metre_mrem=metre_mrem,
            wipe_dpm=wipe_dpm,
            received_by=received_by,
        )
        return self._receipts.add(receipt)

    def require_clean(self, reference: str) -> PackageReceipt:
        """The receipt, or a stop because the package failed its survey."""
        receipt = self._receipts.get(reference)
        failed = receipt.failure()
        if failed is not None:
            raise SafetyError(
                "package-failed",
                f"that package must not be opened: {failed}",
                reference=reference,
            )
        return receipt

    def link(self, generator_id: str, reference: str) -> None:
        """Record which package a column came out of."""
        self._receipts.get(reference)
        self._receipts.link_generator(generator_id, reference)

    def package_of(self, generator_id: str) -> str | None:
        return self._receipts.package_of(generator_id)

    def on_day(self, day: dt.date) -> list[PackageReceipt]:
        return self._receipts.on_day(day, self._tz)

    def failures(self) -> list[PackageReceipt]:
        return self._receipts.failures()
