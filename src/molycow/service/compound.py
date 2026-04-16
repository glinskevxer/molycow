"""Making up a batch: how much eluate goes into which cold kit, and when.

The technologist asks for an activity, not a volume. The volume falls out of
the eluate's concentration at the moment the vial is actually made up, which
is why the same order made up half an hour later takes more millilitres out of
the same elution vial.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import NotFoundError, RuleError
from molycow.formulary import Formula, formula
from molycow.model.kit import Batch, KitLot
from molycow.service.breakthrough import BreakthroughService
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.generators import ElutionRepository
from molycow.store.kits import BatchRepository, KitLotRepository
from molycow.units import Activity, Volume


@dataclass(frozen=True)
class Plan:
    """What a prep would take, worked out before anything is drawn."""

    formula: Formula
    kit_lot: KitLot
    elution_id: str
    volume: Volume
    eluate_volume: Volume
    activity: Activity
    made_at: dt.datetime

    @property
    def saline(self) -> Volume:
        return self.volume - self.eluate_volume


class CompoundService:
    """The bench, between the elution vial and the cold kit."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._elutions = ElutionRepository(book)
        self._lots = KitLotRepository(book)
        self._batches = BatchRepository(book)
        self._release = BreakthroughService(book)
        self._audit = AuditRepository(book)

    def drawn_from(self, elution_id: str) -> Volume:
        """How much has already been taken out of an elution vial."""
        taken = Volume.zero()
        for batch in self._batches.for_elution(elution_id):
            taken = taken + batch.eluate_volume
        return taken

    def remaining_in(self, elution_id: str) -> Volume:
        """What is left in the elution vial to draw with."""
        elution = self._elutions.get(elution_id)
        return elution.volume - self.drawn_from(elution_id)

    def plan(
        self,
        code: str,
        elution_id: str,
        at: dt.datetime,
        wanted: Activity,
        volume: Volume | None = None,
    ) -> Plan:
        """Work out the prep without writing anything down.

        ``volume`` is what the finished vial is made up to. Saline covers the
        difference between it and the eluate the activity actually needs, which
        is what lets a small activity still be made up to the volume the insert
        wants.
        """
        monograph = formula(code)
        elution = self._elutions.get(elution_id)
        if not self._release.may_draw(elution_id, at):
            raise RuleError(
                "eluate-not-released",
                "that eluate may not be drawn from at that moment",
                elution=elution_id,
            )
        lot = self._lots.oldest_in_date(monograph.code, day_of(at, self._tz))
        if lot is None:
            raise NotFoundError("no kit of that sort is in date", kit=monograph.code)
        eluate_volume = elution.concentration_at(at).volume_for(wanted)
        if eluate_volume.is_zero():
            raise RuleError(
                "prep-volume", "that activity works out at no volume at all", kit=monograph.code
            )
        made_up = volume if volume is not None else max(eluate_volume, monograph.min_volume)
        if eluate_volume > made_up:
            raise RuleError(
                "prep-volume",
                "that activity needs more eluate than the vial is made up to",
                kit=monograph.code,
                eluate=str(eluate_volume),
                volume=str(made_up),
            )
        monograph.check(wanted, made_up)
        remaining = self.remaining_in(elution_id)
        if eluate_volume > remaining:
            raise RuleError(
                "eluate-short",
                "there is not enough left in that elution vial",
                elution=elution_id,
                wanted=str(eluate_volume),
                left=str(remaining),
            )
        return Plan(monograph, lot, elution_id, made_up, eluate_volume, wanted, at)

    def compound(
        self,
        code: str,
        elution_id: str,
        at: dt.datetime,
        wanted: Activity,
        made_by: str,
        volume: Volume | None = None,
    ) -> Batch:
        """Make the batch up and write it in the book."""
        prepared = self.plan(code, elution_id, at, wanted, volume)
        batch = Batch(
            id=self._batches.next_id(day_of(at, self._tz)),
            kit_lot_id=prepared.kit_lot.id,
            elution_id=elution_id,
            code=prepared.formula.code,
            made_at=at,
            activity=prepared.activity,
            volume=prepared.volume,
            eluate_volume=prepared.eluate_volume,
            made_by=made_by,
        )
        with self._book.atomic():
            self._batches.add(batch)
            self._audit.record(
                at,
                made_by,
                "compounded",
                batch.id,
                f"{batch.activity.format('mci', 1)} of {batch.code} from {elution_id}",
            )
        return batch

    def ready(self, at: dt.datetime, code: str | None = None) -> list[Batch]:
        """Batches that may be drawn from right now, strongest first."""
        found = [one for one in self._batches.in_date_at(at, code) if one.hold_reason(at) is None]
        return sorted(found, key=lambda one: one.concentration_at(at).uci_per_ml, reverse=True)

    def held(self, at: dt.datetime) -> list[tuple[Batch, str]]:
        """Batches on the bench that nothing may be drawn from, and why."""
        held: list[tuple[Batch, str]] = []
        for batch in self._batches.all():
            reason = batch.hold_reason(at)
            if reason is not None and batch.made_at <= at:
                held.append((batch, reason))
        return held
