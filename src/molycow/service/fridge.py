"""The fridge round, and what an open excursion stops.

A refrigerated kit cannot be compounded while an excursion is open. Not
because the kit is necessarily spoiled, but because nobody has said yet
whether it is, and a batch made in the meantime cannot be unmade.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import RuleError
from molycow.model.fridge import FridgeReading
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.fridge import FridgeRepository


class FridgeService:
    """The thermometer on the door."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._readings = FridgeRepository(book)
        self._audit = AuditRepository(book)

    def record(self, at: dt.datetime, celsius: Decimal, read_by: str) -> FridgeReading:
        """Write a reading down."""
        reading = FridgeReading(read_at=at, celsius=celsius, read_by=read_by)
        self._readings.add(reading)
        return reading

    def review(self, read_at: dt.datetime, at: dt.datetime, by: str) -> FridgeReading:
        """Close an excursion by saying who looked at it."""
        return self._readings.review(read_at, at, by)

    def open_excursions(self) -> list[FridgeReading]:
        return self._readings.open_excursions()

    def is_clear(self) -> bool:
        """Whether the fridge has nothing outstanding against it."""
        return not self._readings.open_excursions()

    def require_clear(self, code: str) -> None:
        """Refuse to compound a refrigerated kit while an excursion is open."""
        open_ones = self._readings.open_excursions()
        if not open_ones:
            return
        worst = open_ones[0]
        raise RuleError(
            "fridge-excursion",
            "the fridge has an excursion nobody has reviewed",
            kit=code,
            reading=f"{worst.celsius} C at {worst.read_at:%Y-%m-%d %H:%M}",
        )

    def readings_on(self, day: dt.date) -> list[FridgeReading]:
        return self._readings.on_day(day, self._tz)

    def latest(self) -> FridgeReading | None:
        return self._readings.latest()
