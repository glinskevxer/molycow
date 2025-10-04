"""Decay in storage, which is how nearly all of this waste leaves the building.

Nothing is disposed of because it looks cold. A container is held for ten half
lives of the longest lived thing that ever went into it, and then it is
surveyed and it has to read background before the label comes off. A vial of
technetium is three days. A capsule of iodine is eighty.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from molycow.decay import decay_between
from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.nuclides import Nuclide, nuclide
from molycow.units import Activity

HALF_LIVES_HELD = 10


class ContainerKind(Enum):
    """What sort of waste goes in it."""

    SHARPS = "sharps"
    DRY = "dry"
    LIQUID = "liquid"
    VIALS = "vials"

    @property
    def takes_sharps(self) -> bool:
        return self is ContainerKind.SHARPS


@dataclass(frozen=True)
class WasteItem:
    """One thing dropped into a container."""

    symbol: str
    activity: Activity
    added_at: dt.datetime
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", nuclide(self.symbol).symbol)
        if self.activity.is_zero():
            raise ValidationError("nothing with no activity needs a decay container")
        if not self.source.strip():
            raise ValidationError("a waste item says where it came from")

    @property
    def nuclide(self) -> Nuclide:
        return nuclide(self.symbol)

    def activity_at(self, moment: dt.datetime) -> Activity:
        if moment < self.added_at:
            return Activity.zero()
        return decay_between(self.activity, self.nuclide, self.added_at, moment)

    @property
    def clear_at(self) -> dt.datetime:
        """When this item alone has been held its ten half lives."""
        hours = self.nuclide.half_life_hours * Decimal(HALF_LIVES_HELD)
        return self.added_at + dt.timedelta(hours=float(hours))


@dataclass(frozen=True)
class Container:
    """One decay in storage container, from the day it was opened."""

    id: str
    kind: ContainerKind
    opened_at: dt.datetime
    items: tuple[WasteItem, ...] = ()
    closed_at: dt.datetime | None = None
    disposed_at: dt.datetime | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.CONTAINER)
        for item in self.items:
            if item.added_at < self.opened_at:
                raise ValidationError(
                    "something went in before the container was opened",
                    id=self.id,
                    source=item.source,
                )
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValidationError("that container was closed before it was opened", id=self.id)
        if self.disposed_at is not None and self.closed_at is None:
            raise ValidationError("a container is closed before it is disposed of", id=self.id)

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    @property
    def is_disposed(self) -> bool:
        return self.disposed_at is not None

    def activity_at(self, moment: dt.datetime) -> Activity:
        total = Activity.zero()
        for item in self.items:
            total = total + item.activity_at(moment)
        return total

    @property
    def longest_lived(self) -> Nuclide | None:
        if not self.items:
            return None
        return max((item.nuclide for item in self.items), key=lambda one: one.half_life_hours)

    @property
    def clear_at(self) -> dt.datetime | None:
        """When the last thing in it has been held its ten half lives."""
        if not self.items:
            return None
        return max(item.clear_at for item in self.items)

    def is_held_long_enough(self, moment: dt.datetime) -> bool:
        clear = self.clear_at
        return clear is not None and moment >= clear

    def hold_reason(self, moment: dt.datetime) -> str | None:
        """Why this container may not be disposed of yet."""
        if not self.items:
            return "nothing has gone in it"
        if not self.is_closed:
            return "still open"
        if not self.is_held_long_enough(moment):
            return "not held ten half lives yet"
        return None

    def with_item(self, item: WasteItem) -> Container:
        if self.is_closed:
            raise ValidationError("that container is closed", id=self.id)
        return Container(
            id=self.id,
            kind=self.kind,
            opened_at=self.opened_at,
            items=(*self.items, item),
            closed_at=None,
            disposed_at=None,
        )

    def closed(self, at: dt.datetime) -> Container:
        if self.is_closed:
            raise ValidationError("that container is already closed", id=self.id)
        if not self.items:
            raise ValidationError("an empty container is not closed, it is unused", id=self.id)
        return Container(self.id, self.kind, self.opened_at, self.items, at, None)
