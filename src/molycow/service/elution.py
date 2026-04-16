"""Milking the generator, and what the pharmacy is allowed to accept from it.

The expected activity is worked out before the vial is measured, because a
number that is worked out afterwards always agrees with the measurement. What
comes off the column is compared against it, and a poor yield stops the eluate
being used until somebody has looked at the column.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import RuleError
from molycow.ingrowth import DAUGHTER
from molycow.model.generator import Elution, Generator
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.generators import ElutionRepository, GeneratorRepository
from molycow.units import Activity, Volume

POOR_YIELD = Decimal("0.70")
LOW_YIELD = Decimal("0.85")


@dataclass(frozen=True)
class Milking:
    """One elution, with the reading that decides whether it can be used."""

    elution: Elution
    generator: Generator
    note: str | None

    @property
    def efficiency(self) -> Decimal:
        return self.elution.efficiency

    @property
    def percent(self) -> Decimal:
        return (self.efficiency * Decimal(100)).quantize(Decimal("0.1"))


class ElutionService:
    """The morning milking, and the ones after it."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._generators = GeneratorRepository(book)
        self._elutions = ElutionRepository(book)
        self._audit = AuditRepository(book)

    def expected_from(self, generator_id: str, at: dt.datetime) -> Activity:
        """What the column should give up if it is milked now."""
        column = self._generators.get(generator_id)
        last = self._elutions.last_for(generator_id)
        residual = None
        if last is not None:
            residual = last.expected - last.activity if last.expected > last.activity else None
        return column.expectation_at(None if last is None else last.drawn_at, at, residual)

    def milk(
        self,
        generator_id: str,
        at: dt.datetime,
        volume: Volume,
        activity: Activity,
        force: bool = False,
        milked_by: str = "the hot lab",
    ) -> Milking:
        """Record an elution against a column."""
        column = self._generators.get(generator_id)
        day = day_of(at, self._tz)
        if not column.is_in_date(day):
            raise RuleError(
                "generator-in-date",
                "that column cannot be milked on that day",
                generator=generator_id,
                day=day.isoformat(),
                expires_on=column.expires_on.isoformat(),
            )
        last = self._elutions.last_for(generator_id)
        if last is not None and at <= last.drawn_at:
            raise RuleError(
                "elution-order",
                "that column was already milked at or after that moment",
                generator=generator_id,
                last=last.id,
            )
        expected = self.expected_from(generator_id, at)
        residual = Activity.zero()
        if last is not None and last.expected > last.activity:
            residual = last.expected - last.activity
        elution = Elution(
            id=self._elutions.next_id(day),
            generator_id=generator_id,
            drawn_at=at,
            volume=volume,
            activity=activity,
            expected=expected,
            residual=residual,
        )
        note = self._read_yield(elution, force)
        with self._book.atomic():
            self._elutions.add(elution)
            self._audit.record(
                at,
                milked_by,
                "milked",
                elution.id,
                f"{elution.activity.format('mci', 1)} from {generator_id}",
            )
        return Milking(elution, column, note)

    def _read_yield(self, elution: Elution, force: bool) -> str | None:
        share = elution.efficiency
        if share < POOR_YIELD and not force:
            raise RuleError(
                "elution-yield",
                "that column gave up far less than it should have",
                generator=elution.generator_id,
                expected=str(elution.expected),
                got=str(elution.activity),
            )
        if share < POOR_YIELD:
            return "poor yield, accepted by override"
        if share < LOW_YIELD:
            return "low yield, watch the column"
        if share > Decimal("1.15"):
            return "more came off than was expected, check the calibration"
        return None

    def available_at(self, elution_id: str, at: dt.datetime) -> Activity:
        """What is left in an eluate vial at a moment, zero once it has expired."""
        elution = self._elutions.get(elution_id)
        if not elution.is_in_date_at(at):
            return Activity.zero()
        return elution.activity_at(at)

    def in_date_eluates(self, at: dt.datetime) -> list[Elution]:
        """The eluate vials that may still be drawn from, freshest first."""
        found = [one for one in self._elutions.all() if one.is_in_date_at(at)]
        return sorted(found, key=lambda one: one.drawn_at, reverse=True)

    def strongest_at(self, at: dt.datetime) -> Elution | None:
        """The in date vial with the most activity per millilitre right now."""
        vials = self.in_date_eluates(at)
        if not vials:
            return None
        return max(vials, key=lambda one: one.concentration_at(at).uci_per_ml)

    def daughter_symbol(self) -> str:
        return DAUGHTER.symbol
