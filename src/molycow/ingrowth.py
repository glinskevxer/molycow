"""How much technetium is sitting in the generator, and when.

A molybdenum-99 generator is milked, and what comes out is the technetium that
grew in since the last time it was milked. The parent decays at its own pace
underneath, so the amount available is not a simple decay curve and cannot be
worked out by decaying the last elution forward.

The branching fraction is the share of molybdenum decays that land on the
metastable state rather than going straight to ground. The rest never appear
in an eluate at all.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, localcontext

from molycow.clock import hours_between
from molycow.decay import WORKING_PRECISION, decay_constant, decay_over
from molycow.errors import ValidationError
from molycow.nuclides import nuclide
from molycow.units import Activity

BRANCHING = Decimal("0.8781")

PARENT = nuclide("Mo-99")
DAUGHTER = nuclide("Tc-99m")


def _exp(value: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        return value.exp()


def ingrowth_factor(hours: Decimal) -> Decimal:
    """The share of a parent activity that shows up as daughter after ``hours``.

    This is the Bateman result for a two step chain, with the branching
    fraction folded in. Multiply the parent activity at the last elution by it.
    """
    if hours < 0:
        raise ValidationError("ingrowth does not run backwards", hours=str(hours))
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        parent_lambda = decay_constant(PARENT)
        daughter_lambda = decay_constant(DAUGHTER)
        ratio = daughter_lambda / (daughter_lambda - parent_lambda)
        return BRANCHING * ratio * (_exp(-parent_lambda * hours) - _exp(-daughter_lambda * hours))


def available(
    parent_at_elution: Activity, hours: Decimal, residual: Activity | None = None
) -> Activity:
    """The technetium in the column ``hours`` after an elution.

    ``residual`` is whatever the last elution failed to wash out, which decays
    on its own schedule underneath the fresh ingrowth.
    """
    grown = parent_at_elution.scaled(ingrowth_factor(hours))
    if residual is None or residual.is_zero():
        return grown
    return grown + decay_over(residual, DAUGHTER, hours)


def parent_after(parent_at_elution: Activity, hours: Decimal) -> Activity:
    """What is left of the molybdenum itself."""
    return decay_over(parent_at_elution, PARENT, hours)


def hours_to_maximum() -> Decimal:
    """When the daughter activity peaks after a full strip, in hours.

    Past this point the column is losing technetium faster than it grows it,
    which is why an overnight generator is milked first thing rather than left.
    """
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        parent_lambda = decay_constant(PARENT)
        daughter_lambda = decay_constant(DAUGHTER)
        return (daughter_lambda / parent_lambda).ln() / (daughter_lambda - parent_lambda)


def equilibrium_ratio() -> Decimal:
    """The daughter to parent activity ratio a rested column settles at."""
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        parent_lambda = decay_constant(PARENT)
        daughter_lambda = decay_constant(DAUGHTER)
        return BRANCHING * daughter_lambda / (daughter_lambda - parent_lambda)


@dataclass(frozen=True)
class Expectation:
    """What a column should give up, and what it gave up last time."""

    parent_at_elution: Activity
    hours_rested: Decimal
    residual: Activity

    @property
    def expected(self) -> Activity:
        return available(self.parent_at_elution, self.hours_rested, self.residual)

    @property
    def parent_now(self) -> Activity:
        return parent_after(self.parent_at_elution, self.hours_rested)

    def efficiency(self, eluted: Activity) -> Decimal:
        """The share of the expected technetium that actually came off the column."""
        expected = self.expected
        if expected.is_zero():
            raise ValidationError("nothing was expected from this column")
        return eluted.ratio_to(expected)


def expectation(
    parent_at_elution: Activity,
    last_elution: dt.datetime,
    at: dt.datetime,
    residual: Activity | None = None,
) -> Expectation:
    """Build the expectation for a column between two moments."""
    hours = hours_between(last_elution, at)
    if hours < 0:
        raise ValidationError(
            "the column cannot be milked before it was last milked",
            last_elution=last_elution.isoformat(),
            at=at.isoformat(),
        )
    return Expectation(parent_at_elution, hours, residual or Activity.zero())
