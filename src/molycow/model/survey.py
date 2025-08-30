"""Radiation surveys: what the meter read, and what came off on the swab.

Two different measurements with two different limits. A dose rate says how
much radiation is standing in the room. A wipe says how much of it is loose
and can be carried out of the room on a shoe, which is the one that closes a
pharmacy.

Counts from the well counter are turned into disintegrations here, because the
limit is written in disintegrations and a counter that sees a third of them is
the ordinary case rather than the exception.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from molycow.errors import ValidationError
from molycow.ids import Kind, expect

WIPE_LIMIT_DPM = Decimal(2200)
UNRESTRICTED_LIMIT_MREM = Decimal("0.05")
RESTRICTED_LIMIT_MREM = Decimal(5)


class Area(Enum):
    """The places that get surveyed, and how tightly they are held."""

    HOT_LAB = "hot lab"
    DISPENSING = "dispensing bench"
    PACKAGING = "packaging"
    STORAGE = "storage"
    WASTE = "waste store"
    RECEPTION = "reception"
    DOCK = "dock"

    @property
    def is_restricted(self) -> bool:
        """Whether only badged staff go in there."""
        return self not in {Area.RECEPTION, Area.DOCK}

    @property
    def dose_rate_limit(self) -> Decimal:
        return RESTRICTED_LIMIT_MREM if self.is_restricted else UNRESTRICTED_LIMIT_MREM


@dataclass(frozen=True)
class DoseRate:
    """A meter reading in millirem per hour."""

    mrem_per_hour: Decimal

    def __post_init__(self) -> None:
        if self.mrem_per_hour < 0:
            raise ValidationError("a dose rate cannot be negative", reading=str(self.mrem_per_hour))

    @classmethod
    def of(cls, value: object) -> DoseRate:
        return cls(Decimal(str(value)))

    def over(self, limit: Decimal) -> bool:
        return self.mrem_per_hour > limit

    def __str__(self) -> str:
        return f"{self.mrem_per_hour.quantize(Decimal('0.01'))} mrem/h"


@dataclass(frozen=True)
class Wipe:
    """One swab, counted in the well counter."""

    area: Area
    spot: str
    counts: int
    background: int
    efficiency: Decimal

    def __post_init__(self) -> None:
        if self.counts < 0 or self.background < 0:
            raise ValidationError("a count cannot be negative", spot=self.spot)
        if not (Decimal(0) < self.efficiency <= Decimal(1)):
            raise ValidationError(
                "counter efficiency is a fraction of one",
                efficiency=str(self.efficiency),
            )
        if not self.spot.strip():
            raise ValidationError("a wipe names the spot it was taken from")

    @property
    def net_counts(self) -> int:
        return max(self.counts - self.background, 0)

    @property
    def dpm(self) -> Decimal:
        """Disintegrations a minute, which is what the limit is written in."""
        return (Decimal(self.net_counts) / self.efficiency).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )

    def is_clean(self, limit: Decimal = WIPE_LIMIT_DPM) -> bool:
        return self.dpm <= limit


@dataclass(frozen=True)
class Survey:
    """One round of the building, with the readings it produced."""

    id: str
    at: dt.datetime
    surveyed_by: str
    readings: tuple[tuple[Area, DoseRate], ...]
    wipes: tuple[Wipe, ...]

    def __post_init__(self) -> None:
        expect(self.id, Kind.SURVEY)
        if not self.surveyed_by.strip():
            raise ValidationError("a survey is signed by whoever walked it", id=self.id)
        if not self.readings and not self.wipes:
            raise ValidationError("a survey with no readings is not a survey", id=self.id)

    def hot_areas(self) -> list[tuple[Area, DoseRate]]:
        """Areas reading over their own limit."""
        return [(area, rate) for area, rate in self.readings if rate.over(area.dose_rate_limit)]

    def dirty_wipes(self, limit: Decimal = WIPE_LIMIT_DPM) -> list[Wipe]:
        return [wipe for wipe in self.wipes if not wipe.is_clean(limit)]

    def passes(self, limit: Decimal = WIPE_LIMIT_DPM) -> bool:
        return not self.hot_areas() and not self.dirty_wipes(limit)

    @property
    def worst_reading(self) -> DoseRate | None:
        if not self.readings:
            return None
        return max((rate for _, rate in self.readings), key=lambda one: one.mrem_per_hour)

    def failure(self, limit: Decimal = WIPE_LIMIT_DPM) -> str | None:
        hot = self.hot_areas()
        if hot:
            area, rate = hot[0]
            return f"{area.value} reading {rate}"
        dirty = self.dirty_wipes(limit)
        if dirty:
            return f"{dirty[0].spot} wiped {dirty[0].dpm} dpm"
        return None
