"""The checks that say whether a dose calibrator can be believed.

Four of them, and they are not the same test at four intervals. Constancy asks
whether the reading has moved since yesterday, against a long lived sealed
source. Accuracy asks whether it agrees with a certificate. Linearity asks
whether it is still right at a thousandth of this morning's activity, and it is
the only one that cannot be answered with a single reading, because the whole
question is about the shape of the curve.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from molycow.clock import hours_between
from molycow.decay import decay_between
from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.nuclides import nuclide
from molycow.units import Activity

PERCENT = Decimal("0.1")


def deviation(measured: Activity, expected: Activity) -> Decimal:
    """How far a reading is off what it should be, as a signed percentage."""
    if expected.is_zero():
        raise ValidationError("a reading cannot be compared against nothing")
    share = (measured.uci - expected.uci) / expected.uci * Decimal(100)
    return share.quantize(PERCENT, rounding=ROUND_HALF_UP)


class CheckKind(Enum):
    """The four checks, with the tolerance and the interval each is held to."""

    CONSTANCY = "constancy"
    ACCURACY = "accuracy"
    LINEARITY = "linearity"
    GEOMETRY = "geometry"

    @property
    def tolerance_percent(self) -> Decimal:
        return {
            CheckKind.CONSTANCY: Decimal(10),
            CheckKind.ACCURACY: Decimal(5),
            CheckKind.LINEARITY: Decimal(5),
            CheckKind.GEOMETRY: Decimal(2),
        }[self]

    @property
    def interval_days(self) -> int | None:
        """How often it comes round, or ``None`` for one that is done at install."""
        return {
            CheckKind.CONSTANCY: 1,
            CheckKind.ACCURACY: 365,
            CheckKind.LINEARITY: 92,
            CheckKind.GEOMETRY: None,
        }[self]


@dataclass(frozen=True)
class QcCheck:
    """One reading of a source on an instrument."""

    instrument_id: str
    kind: CheckKind
    at: dt.datetime
    source_serial: str
    expected: Activity
    measured: Activity
    checked_by: str

    def __post_init__(self) -> None:
        expect(self.instrument_id, Kind.INSTRUMENT)
        if not self.source_serial.strip():
            raise ValidationError("a check names the source it was run with")
        if not self.checked_by.strip():
            raise ValidationError("a check is signed by whoever ran it")
        if self.measured.is_zero():
            raise ValidationError("a check that measured nothing is not a check")

    @property
    def deviation_percent(self) -> Decimal:
        return deviation(self.measured, self.expected)

    @property
    def passes(self) -> bool:
        return abs(self.deviation_percent) <= self.kind.tolerance_percent

    def due_again(self) -> dt.date | None:
        """When this check comes round again."""
        every = self.kind.interval_days
        if every is None:
            return None
        return self.at.date() + dt.timedelta(days=every)

    def note(self) -> str:
        verdict = "passed" if self.passes else "FAILED"
        return f"{self.kind.value} {verdict} at {self.deviation_percent}%"


@dataclass(frozen=True)
class LinearityPoint:
    """One reading in a linearity run."""

    at: dt.datetime
    measured: Activity


@dataclass(frozen=True)
class LinearityRun:
    """A source read down over several days, and what the curve says.

    Every later reading is compared against the first one carried forward by
    decay. The run passes when the worst of them is inside tolerance.
    """

    instrument_id: str
    symbol: str
    points: tuple[LinearityPoint, ...]
    checked_by: str

    def __post_init__(self) -> None:
        expect(self.instrument_id, Kind.INSTRUMENT)
        if len(self.points) < 3:
            raise ValidationError(
                "a linearity run needs at least three readings", points=len(self.points)
            )
        moments = [point.at for point in self.points]
        if moments != sorted(moments):
            raise ValidationError("a linearity run has to be in the order it was read")
        if self.points[0].measured.is_zero():
            raise ValidationError("a linearity run cannot start from nothing")

    @property
    def first(self) -> LinearityPoint:
        return self.points[0]

    def expected_at(self, moment: dt.datetime) -> Activity:
        return decay_between(self.first.measured, nuclide(self.symbol), self.first.at, moment)

    def deviations(self) -> list[Decimal]:
        return [deviation(point.measured, self.expected_at(point.at)) for point in self.points]

    @property
    def worst(self) -> Decimal:
        return max(self.deviations(), key=abs)

    def passes(self, tolerance: Decimal = Decimal(5)) -> bool:
        return abs(self.worst) <= tolerance

    @property
    def hours_covered(self) -> Decimal:
        return hours_between(self.first.at, self.points[-1].at)

    def lowest(self) -> Activity:
        return min(point.measured for point in self.points)
