"""What else came off the column, and how long that leaves the vial usable.

Two things are looked for in an eluate. Molybdenum that washed through with
the technetium, and aluminium from the column bed itself. The molybdenum limit
is a ratio at the moment of administration rather than at the moment of the
test, and the ratio climbs all day: the technetium underneath it is decaying
eleven times faster than the molybdenum is. A vial can pass at seven in the
morning and be over the limit by mid afternoon, and that, not the twelve hour
shelf life, is often what ends it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, localcontext

from molycow.clock import hours_between
from molycow.decay import WORKING_PRECISION, decay_constant
from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.nuclides import nuclide
from molycow.units import Activity

MOLY_LIMIT = Decimal("0.15")
ALUMINIUM_LIMIT = Decimal("10")

PARENT = nuclide("Mo-99")
DAUGHTER = nuclide("Tc-99m")


def ratio_growth_per_hour() -> Decimal:
    """How fast the molybdenum to technetium ratio climbs, per hour."""
    return decay_constant(DAUGHTER) - decay_constant(PARENT)


def ratio_at(start_ratio: Decimal, hours: Decimal) -> Decimal:
    """The ratio ``hours`` after it was measured."""
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        return start_ratio * (ratio_growth_per_hour() * hours).exp()


def hours_until_limit(start_ratio: Decimal, limit: Decimal = MOLY_LIMIT) -> Decimal:
    """How long a vial at ``start_ratio`` stays under the limit."""
    if start_ratio <= 0:
        raise ValidationError(
            "a ratio has to be above zero to be projected", ratio=str(start_ratio)
        )
    if start_ratio >= limit:
        return Decimal(0)
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        return (limit / start_ratio).ln() / ratio_growth_per_hour()


@dataclass(frozen=True)
class Breakthrough:
    """One test of an eluate, run on the vial before anything is drawn from it."""

    elution_id: str
    tested_at: dt.datetime
    moly: Activity
    technetium: Activity
    aluminium_ppm: Decimal
    tested_by: str

    def __post_init__(self) -> None:
        expect(self.elution_id, Kind.ELUTION)
        if self.technetium.is_zero():
            raise ValidationError(
                "a breakthrough test needs the technetium it was measured against",
                elution=self.elution_id,
            )
        if self.aluminium_ppm < 0:
            raise ValidationError("aluminium cannot be negative", elution=self.elution_id)
        if not self.tested_by.strip():
            raise ValidationError("a test is signed by whoever ran it", elution=self.elution_id)

    @property
    def ratio(self) -> Decimal:
        """Microcuries of molybdenum for each millicurie of technetium, at the test."""
        return self.moly.uci / self.technetium.mci

    def ratio_at(self, moment: dt.datetime) -> Decimal:
        """The ratio at a later moment, refusing one before the test."""
        hours = hours_between(self.tested_at, moment)
        if hours < 0:
            raise ValidationError(
                "the ratio cannot be read before the test", elution=self.elution_id
            )
        return ratio_at(self.ratio, hours)

    @property
    def moly_passes(self) -> bool:
        return self.ratio < MOLY_LIMIT

    @property
    def aluminium_passes(self) -> bool:
        return self.aluminium_ppm <= ALUMINIUM_LIMIT

    @property
    def passes(self) -> bool:
        return self.moly_passes and self.aluminium_passes

    @property
    def usable_until(self) -> dt.datetime:
        """The moment the vial's ratio reaches the limit."""
        hours = hours_until_limit(self.ratio)
        return self.tested_at + dt.timedelta(hours=float(hours))

    def is_usable_at(self, moment: dt.datetime) -> bool:
        if not self.aluminium_passes:
            return False
        return moment <= self.usable_until

    def failure(self) -> str | None:
        """Why this test failed, in the words the log uses."""
        if not self.moly_passes:
            return "molybdenum breakthrough over the limit"
        if not self.aluminium_passes:
            return "aluminium over the limit"
        return None
