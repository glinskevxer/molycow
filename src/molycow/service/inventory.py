"""What is actually in the building at a moment, and what the licence allows.

Everything is decayed to the same moment and added up by nuclide. That is the
only way the possession limit means anything, because a generator delivered on
Friday and an eluate drawn this morning are different numbers on different
clocks until they are all brought to now.

A dose that has been signed for at a hospital is not here any more. A dose
sitting in a packed box on the dock still is.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import RuleError
from molycow.formulary import formula
from molycow.model.licence import PossessionLimit
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.generators import ElutionRepository, GeneratorRepository
from molycow.store.kits import BatchRepository
from molycow.store.licence import LicenceRepository
from molycow.store.shipments import ShipmentRepository
from molycow.store.waste import ContainerRepository
from molycow.units import Activity, Volume


@dataclass(frozen=True)
class Holding:
    """What one nuclide adds up to, and where it is sitting."""

    symbol: str
    total: Activity
    by_place: dict[str, Activity]

    def place(self, name: str) -> Activity:
        return self.by_place.get(name, Activity.zero())


@dataclass(frozen=True)
class LimitCheck:
    """A holding against the ceiling the licence puts on it."""

    holding: Holding
    limit: PossessionLimit | None

    @property
    def over(self) -> bool:
        return self.limit is not None and not self.limit.allows(self.holding.total)

    @property
    def share(self) -> Decimal | None:
        if self.limit is None:
            return None
        return self.limit.share_used(self.holding.total)


class InventoryService:
    """The possession question, answered at a moment."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._generators = GeneratorRepository(book)
        self._elutions = ElutionRepository(book)
        self._batches = BatchRepository(book)
        self._doses = DoseRepository(book)
        self._shipments = ShipmentRepository(book)
        self._containers = ContainerRepository(book)
        self._licence = LicenceRepository(book)

    def holdings(self, at: dt.datetime) -> dict[str, Holding]:
        """Everything on the premises at a moment, by nuclide."""
        places: dict[str, dict[str, Activity]] = {}
        self._add_generators(places, at)
        self._add_eluates(places, at)
        self._add_batches(places, at)
        self._add_doses(places, at)
        self._add_waste(places, at)
        return {
            symbol: Holding(symbol, self._total(by_place), by_place)
            for symbol, by_place in places.items()
        }

    def _add(
        self,
        places: dict[str, dict[str, Activity]],
        symbol: str,
        place: str,
        activity: Activity,
    ) -> None:
        if activity.is_zero():
            return
        per_place = places.setdefault(symbol, {})
        per_place[place] = per_place.get(place, Activity.zero()) + activity

    def _add_generators(self, places: dict[str, dict[str, Activity]], at: dt.datetime) -> None:
        for generator in self._generators.all():
            if generator.retired_on is not None:
                continue
            self._add(places, "Mo-99", "generators", generator.parent_at(at))

    def _add_eluates(self, places: dict[str, dict[str, Activity]], at: dt.datetime) -> None:
        for elution in self._elutions.all():
            if at < elution.drawn_at:
                continue
            left = self._left_in_elution(elution.id, elution.volume)
            if left.is_zero():
                continue
            self._add(places, "Tc-99m", "eluate", elution.concentration_at(at).activity_in(left))

    def _add_batches(self, places: dict[str, dict[str, Activity]], at: dt.datetime) -> None:
        for batch in self._batches.all():
            if at < batch.made_at:
                continue
            left = self._left_in_batch(batch.id, batch.volume)
            if left.is_zero():
                continue
            symbol = formula(batch.code).nuclide
            self._add(places, symbol, "batches", batch.concentration_at(at).activity_in(left))

    def _add_doses(self, places: dict[str, dict[str, Activity]], at: dt.datetime) -> None:
        for dose in self._doses.all():
            if at < dose.drawn_at or self._has_left(dose.id, at):
                continue
            self._add(places, formula(dose.code).nuclide, "doses", dose.activity_at(at))

    def _add_waste(self, places: dict[str, dict[str, Activity]], at: dt.datetime) -> None:
        for container in self._containers.all():
            if container.is_disposed:
                continue
            for item in container.items:
                self._add(places, item.symbol, "waste", item.activity_at(at))

    def _total(self, by_place: dict[str, Activity]) -> Activity:
        total = Activity.zero()
        for activity in by_place.values():
            total = total + activity
        return total

    def _left_in_elution(self, elution_id: str, volume: Volume) -> Volume:
        taken = Volume.zero()
        for batch in self._batches.for_elution(elution_id):
            taken = taken + batch.eluate_volume
        return volume - taken if volume > taken else Volume.zero()

    def _left_in_batch(self, batch_id: str, volume: Volume) -> Volume:
        taken = Volume.zero()
        for dose in self._doses.for_batch(batch_id):
            taken = taken + dose.volume
        return volume - taken if volume > taken else Volume.zero()

    def _has_left(self, dose_id: str, at: dt.datetime) -> bool:
        """A dose is off the premises once its box has been signed for."""
        box = self._shipments.holding(dose_id)
        if box is None or box.delivered_at is None:
            return False
        return at >= box.delivered_at

    def holding_of(self, symbol: str, at: dt.datetime) -> Activity:
        found = self.holdings(at).get(symbol)
        return Activity.zero() if found is None else found.total

    def check(self, at: dt.datetime) -> list[LimitCheck]:
        """Every nuclide in the building against its ceiling, worst first."""
        checks = [
            LimitCheck(holding, self._licence.find(symbol))
            for symbol, holding in self.holdings(at).items()
        ]
        return sorted(checks, key=lambda one: one.share or Decimal(0), reverse=True)

    def over_limit(self, at: dt.datetime) -> list[LimitCheck]:
        return [one for one in self.check(at) if one.over]

    def require_room_for(self, symbol: str, activity: Activity, at: dt.datetime) -> Activity:
        """The headroom left for a delivery, or a refusal."""
        limit = self._licence.find(symbol)
        if limit is None:
            raise RuleError(
                "licence-nuclide", "the licence does not name that nuclide", symbol=symbol
            )
        holding = self.holding_of(symbol, at)
        if not limit.allows(holding + activity):
            raise RuleError(
                "possession-limit",
                "that delivery would put the pharmacy over its possession limit",
                symbol=symbol,
                holding=str(holding),
                delivery=str(activity),
                limit=str(limit.limit),
            )
        return limit.headroom(holding + activity)
