"""The instruments in the hot lab, and the sealed sources they are checked with.

Every activity in this package came off a dose calibrator, so the calibrator
is a record in its own right. A sealed check source is the other half: it is
the only thing in the building whose activity is known without measuring it,
because the maker certified it and it has been decaying on a shelf ever since.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum

from molycow.clock import combine, zone
from molycow.decay import decay_between
from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.nuclides import Nuclide, Use, nuclide
from molycow.units import Activity


class InstrumentKind(Enum):
    """What the instrument is for."""

    DOSE_CALIBRATOR = "dose calibrator"
    WELL_COUNTER = "well counter"
    SURVEY_METER = "survey meter"
    AREA_MONITOR = "area monitor"

    @property
    def needs_daily_check(self) -> bool:
        """Whether it is checked before the first dose of the day goes out."""
        return self in {InstrumentKind.DOSE_CALIBRATOR, InstrumentKind.SURVEY_METER}


@dataclass(frozen=True)
class Instrument:
    """One piece of measuring equipment."""

    id: str
    kind: InstrumentKind
    maker: str
    model: str
    serial: str
    installed_on: dt.date
    calibrated_on: dt.date
    retired_on: dt.date | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.INSTRUMENT)
        if not self.serial.strip():
            raise ValidationError("an instrument needs its serial number", id=self.id)
        if self.calibrated_on < self.installed_on:
            raise ValidationError(
                "that instrument was calibrated before it was installed", id=self.id
            )
        if self.retired_on is not None and self.retired_on < self.installed_on:
            raise ValidationError("that instrument was retired before it arrived", id=self.id)

    @property
    def calibration_due(self) -> dt.date:
        """The maker's calibration is good for a year."""
        return self.calibrated_on.replace(year=self.calibrated_on.year + 1)

    def is_in_calibration(self, day: dt.date) -> bool:
        return self.calibrated_on <= day < self.calibration_due

    def is_in_service(self, day: dt.date) -> bool:
        if day < self.installed_on:
            return False
        return self.retired_on is None or day <= self.retired_on

    def is_usable_on(self, day: dt.date) -> bool:
        return self.is_in_service(day) and self.is_in_calibration(day)

    def unusable_reason(self, day: dt.date) -> str | None:
        if not self.is_in_service(day):
            return "not in service that day"
        if not self.is_in_calibration(day):
            return "annual calibration has run out"
        return None

    def __str__(self) -> str:
        return f"{self.maker} {self.model} ({self.serial})"


@dataclass(frozen=True)
class CheckSource:
    """A sealed source, certified once and decaying ever since."""

    serial: str
    symbol: str
    certified_activity: Activity
    certified_on: dt.date
    retired_on: dt.date | None = None

    def __post_init__(self) -> None:
        found = nuclide(self.symbol)
        if found.use is not Use.CHECK_SOURCE:
            raise ValidationError("that nuclide is not a sealed check source", symbol=self.symbol)
        object.__setattr__(self, "symbol", found.symbol)
        if self.certified_activity.is_zero():
            raise ValidationError("a check source needs its certified activity", serial=self.serial)
        if not self.serial.strip():
            raise ValidationError("a check source needs its serial", symbol=self.symbol)

    @property
    def nuclide(self) -> Nuclide:
        return nuclide(self.symbol)

    def activity_on(self, day: dt.date) -> Activity:
        """What the source reads on a day, decayed from its certificate."""
        if day < self.certified_on:
            raise ValidationError(
                "a source has no reading before it was certified",
                serial=self.serial,
                day=day.isoformat(),
            )
        tz = zone()
        noon = dt.time(12, 0)
        return decay_between(
            self.certified_activity,
            self.nuclide,
            combine(self.certified_on, noon, tz),
            combine(day, noon, tz),
        )

    def is_in_use_on(self, day: dt.date) -> bool:
        if day < self.certified_on:
            return False
        return self.retired_on is None or day <= self.retired_on
