"""Testing an eluate and deciding how long it may be drawn from.

Two clocks run on a vial and the earlier one wins. The shelf life is twelve
hours from the elution. The molybdenum ratio climbs from the moment of the
test and the vial is finished when it reaches the limit. A vial with no test
at all cannot be drawn from, whatever the clock says.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ReleaseError
from molycow.model.breakthrough import Breakthrough
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.breakthrough import BreakthroughRepository
from molycow.store.generators import ElutionRepository
from molycow.units import Activity


@dataclass(frozen=True)
class Release:
    """Whether a vial may be drawn from, and until when."""

    elution_id: str
    good_until: dt.datetime
    ends_because: str

    def covers(self, moment: dt.datetime) -> bool:
        return moment <= self.good_until


class BreakthroughService:
    """The bench test that lets an eluate be used."""

    def __init__(self, book: Book) -> None:
        self._book = book
        self._tests = BreakthroughRepository(book)
        self._elutions = ElutionRepository(book)
        self._audit = AuditRepository(book)

    def test(
        self,
        elution_id: str,
        tested_at: dt.datetime,
        moly: Activity,
        aluminium_ppm: Decimal,
        tested_by: str,
    ) -> Breakthrough:
        """Run the test against the technetium the vial actually holds now."""
        elution = self._elutions.get(elution_id)
        if tested_at < elution.drawn_at:
            raise ReleaseError(
                "test-after-elution",
                "an eluate cannot be tested before it was drawn",
                elution=elution_id,
            )
        reading = Breakthrough(
            elution_id=elution_id,
            tested_at=tested_at,
            moly=moly,
            technetium=elution.activity_at(tested_at),
            aluminium_ppm=aluminium_ppm,
            tested_by=tested_by,
        )
        failed = reading.failure()
        with self._book.atomic():
            self._tests.add(reading)
            self._audit.record(
                tested_at,
                tested_by,
                "tested",
                elution_id,
                failed or f"{reading.ratio:.4f} uCi/mCi",
            )
        return reading

    def release(self, elution_id: str) -> Release:
        """How long the vial may be drawn from, and what ends it."""
        elution = self._elutions.get(elution_id)
        reading = self._tests.find(elution_id)
        if reading is None:
            raise ReleaseError(
                "eluate-untested",
                "that eluate has not been tested and cannot be used",
                elution=elution_id,
            )
        failed = reading.failure()
        if failed is not None:
            raise ReleaseError("eluate-failed", failed, elution=elution_id)
        shelf = elution.expires_at
        ratio = reading.usable_until
        if ratio < shelf:
            return Release(elution_id, ratio, "molybdenum ratio reaches the limit")
        return Release(elution_id, shelf, "twelve hour shelf life")

    def may_draw(self, elution_id: str, at: dt.datetime) -> bool:
        """Whether a syringe may be filled from this vial right now."""
        try:
            return (
                self.release(elution_id).covers(at)
                and at >= self._elutions.get(elution_id).drawn_at
            )
        except ReleaseError:
            return False

    def untested(self) -> list[str]:
        """Elutions with no test against them, oldest first."""
        tested = {one.elution_id for one in self._tests.all()}
        return [one.id for one in self._elutions.all() if one.id not in tested]
