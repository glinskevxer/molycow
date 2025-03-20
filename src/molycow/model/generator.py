"""The generator on the bench, and every time it was milked.

A generator arrives with a calibration: how much molybdenum-99 it held at a
stated moment. Everything else about it is worked out from there, because the
column is sealed and nobody ever measures the parent directly.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from molycow.clock import hours_between
from molycow.decay import decay_between
from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.ingrowth import DAUGHTER, PARENT, expectation
from molycow.units import Activity, Concentration, Volume

ELUATE_HOURS = 12
MAX_ELUATE_ML = Volume(Decimal(30))


@dataclass(frozen=True)
class Generator:
    """One molybdenum-99 column, from the day it lands to the day it goes back."""

    id: str
    serial: str
    maker: str
    calibrated_at: dt.datetime
    calibrated_activity: Activity
    received_on: dt.date
    expires_on: dt.date
    retired_on: dt.date | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.GENERATOR)
        if not self.serial.strip():
            raise ValidationError("a generator needs the maker's serial", id=self.id)
        if self.calibrated_activity.is_zero():
            raise ValidationError("a generator with no calibration is no use", id=self.id)
        if self.expires_on < self.received_on:
            raise ValidationError(
                "that generator expires before it arrived",
                id=self.id,
                received_on=self.received_on.isoformat(),
                expires_on=self.expires_on.isoformat(),
            )
        if self.retired_on is not None and self.retired_on < self.received_on:
            raise ValidationError("a generator cannot be retired before it arrived", id=self.id)

    def parent_at(self, moment: dt.datetime) -> Activity:
        """The molybdenum left in the column at a moment."""
        return decay_between(self.calibrated_activity, PARENT, self.calibrated_at, moment)

    def is_in_date(self, day: dt.date) -> bool:
        if day > self.expires_on:
            return False
        if self.retired_on is not None and day > self.retired_on:
            return False
        return day >= self.received_on

    def age_days(self, day: dt.date) -> int:
        return (day - self.received_on).days

    def expectation_at(
        self, last_elution: dt.datetime | None, at: dt.datetime, residual: Activity | None = None
    ) -> Activity:
        """What the column should give up now, given when it was last milked.

        A column that has never been milked is treated as having been stripped
        at the maker's calibration, which is what the maker's own chart assumes.
        """
        since = last_elution or self.calibrated_at
        parent = self.parent_at(since)
        return expectation(parent, since, at, residual).expected


@dataclass(frozen=True)
class Elution:
    """One milking of a column."""

    id: str
    generator_id: str
    drawn_at: dt.datetime
    volume: Volume
    activity: Activity
    expected: Activity
    residual: Activity = field(default_factory=Activity.zero)

    def __post_init__(self) -> None:
        expect(self.id, Kind.ELUTION)
        expect(self.generator_id, Kind.GENERATOR)
        if self.volume.is_zero():
            raise ValidationError("an elution with no volume is not an elution", id=self.id)
        if self.volume > MAX_ELUATE_ML:
            raise ValidationError(
                "no elution vial on the bench holds that much",
                id=self.id,
                volume=str(self.volume),
            )
        if self.activity.is_zero():
            raise ValidationError("an elution has to have something in it", id=self.id)

    @property
    def concentration(self) -> Concentration:
        """How much technetium sits in a millilitre of this eluate."""
        return Concentration.of(self.activity, self.volume)

    @property
    def expires_at(self) -> dt.datetime:
        """Eluate is good for twelve hours from the moment it came off."""
        return self.drawn_at + dt.timedelta(hours=ELUATE_HOURS)

    def is_in_date_at(self, moment: dt.datetime) -> bool:
        return self.drawn_at <= moment <= self.expires_at

    def activity_at(self, moment: dt.datetime) -> Activity:
        """What is left in the vial at a later moment."""
        if moment < self.drawn_at:
            raise ValidationError(
                "an eluate has no activity before it was drawn",
                id=self.id,
                moment=moment.isoformat(),
            )
        return decay_between(self.activity, DAUGHTER, self.drawn_at, moment)

    def concentration_at(self, moment: dt.datetime) -> Concentration:
        return Concentration.of(self.activity_at(moment), self.volume)

    @property
    def efficiency(self) -> Decimal:
        """The share of what was expected that actually came off the column."""
        if self.expected.is_zero():
            raise ValidationError("nothing was expected of that column", id=self.id)
        return self.activity.ratio_to(self.expected)

    def hours_since(self, moment: dt.datetime) -> Decimal:
        return hours_between(self.drawn_at, moment)
