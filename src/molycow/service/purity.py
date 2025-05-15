"""Running the strips on a batch and releasing it, or holding it.

The reading is kept in full, both strips and their counts, and the percentage
is written onto the batch as well. The percentage is what everything downstream
compares against a floor; the counts are what an inspector asks for.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ReleaseError
from molycow.model.kit import Batch
from molycow.model.purity import PurityTest, Strip
from molycow.store.book import Book
from molycow.store.kits import BatchRepository
from molycow.store.purity import PurityRepository


@dataclass(frozen=True)
class Reading:
    """A purity test with the batch it belongs to and the verdict."""

    test: PurityTest
    batch: Batch
    released: bool

    @property
    def rcp(self) -> Decimal:
        return self.test.rcp

    @property
    def floor(self) -> Decimal:
        return self.batch.formula.rcp_floor

    def note(self) -> str:
        if self.released:
            return f"{self.rcp}% against a floor of {self.floor}%"
        return f"held at {self.rcp}%, mostly {self.test.worst_impurity()}"


class PurityService:
    """The chromatography bench."""

    def __init__(self, book: Book) -> None:
        self._book = book
        self._tests = PurityRepository(book)
        self._batches = BatchRepository(book)

    def run(
        self,
        batch_id: str,
        tested_at: dt.datetime,
        solvent: Strip,
        saline: Strip,
        tested_by: str,
    ) -> Reading:
        """Record both strips against a batch and write the purity onto it."""
        batch = self._batches.get(batch_id)
        if tested_at < batch.made_at:
            raise ReleaseError(
                "purity-after-prep",
                "a batch cannot be tested before it was made",
                batch=batch_id,
            )
        reading = PurityTest(
            batch_id=batch_id,
            tested_at=tested_at,
            solvent=solvent,
            saline=saline,
            tested_by=tested_by,
        )
        with self._book.atomic():
            self._tests.add(reading)
            tested = self._batches.record_purity(batch_id, reading.rcp)
        return Reading(reading, tested, tested.is_pure_enough)

    def reading_for(self, batch_id: str) -> PurityTest:
        return self._tests.get(batch_id)

    def released(self, batch_id: str) -> bool:
        return self._batches.get(batch_id).is_pure_enough

    def require_released(self, batch_id: str, at: dt.datetime) -> Batch:
        """Get a batch, or say why nothing may be drawn from it."""
        batch = self._batches.get(batch_id)
        held = batch.hold_reason(at)
        if held is not None:
            raise ReleaseError("batch-held", held, batch=batch_id)
        return batch

    def failures(self) -> list[Batch]:
        """Batches that were tested and did not make the floor."""
        return [one for one in self._batches.all() if one.is_tested and not one.is_pure_enough]
