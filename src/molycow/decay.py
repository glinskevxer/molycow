"""Decay correction, which is most of the arithmetic in a nuclear pharmacy.

Everything here is exponential decay of a single nuclide. It is written in
decimal rather than float because the numbers end up on a label a technologist
compares against a dose calibrator reading, and a drifting last digit in a
printed volume is a question nobody should have to answer twice.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, localcontext

from molycow.clock import hours_between
from molycow.errors import ValidationError
from molycow.nuclides import Nuclide
from molycow.units import Activity

LN2 = Decimal("0.69314718055994530941723212145798")

WORKING_PRECISION = 34


def decay_constant(nuclide: Nuclide) -> Decimal:
    """The decay constant in inverse hours."""
    return LN2 / nuclide.half_life_hours


def half_lives_over(nuclide: Nuclide, hours: Decimal) -> Decimal:
    """How many half lives fit in an interval, which may be negative."""
    return hours / nuclide.half_life_hours


def factor_over(nuclide: Nuclide, hours: Decimal) -> Decimal:
    """The fraction of an activity left after ``hours``.

    A negative interval reads backwards and returns a factor above one, which
    is how a precalibrated activity is worked out.
    """
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        return Decimal(2) ** (-half_lives_over(nuclide, hours))


def factor_between(nuclide: Nuclide, frm: dt.datetime, to: dt.datetime) -> Decimal:
    return factor_over(nuclide, hours_between(frm, to))


def decay_over(activity: Activity, nuclide: Nuclide, hours: Decimal) -> Activity:
    """What is left of ``activity`` after ``hours`` of decay."""
    return activity.scaled(factor_over(nuclide, hours))


def decay_between(
    activity: Activity, nuclide: Nuclide, frm: dt.datetime, to: dt.datetime
) -> Activity:
    """Carry an activity from the moment it was measured to another moment."""
    return activity.scaled(factor_between(nuclide, frm, to))


def needed_at(
    wanted: Activity, nuclide: Nuclide, wanted_at: dt.datetime, drawn_at: dt.datetime
) -> Activity:
    """How much has to be in the syringe at ``drawn_at`` to be ``wanted`` at ``wanted_at``.

    This is the number the dispensing bench works to. Drawing early means
    drawing more.
    """
    return decay_between(wanted, nuclide, wanted_at, drawn_at)


def hours_to_reach(nuclide: Nuclide, activity: Activity, target: Activity) -> Decimal:
    """How long until ``activity`` decays to ``target``."""
    if activity.is_zero():
        raise ValidationError("nothing decays from zero activity")
    if target.is_zero():
        raise ValidationError("activity never reaches exactly zero, pick a real target")
    if target > activity:
        raise ValidationError(
            "that target is above the activity already",
            have=str(activity),
            target=str(target),
        )
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        ratio = activity.uci / target.uci
        return nuclide.half_life_hours * (ratio.ln() / LN2)


def moment_reaching(
    nuclide: Nuclide, activity: Activity, measured_at: dt.datetime, target: Activity
) -> dt.datetime:
    """When an activity measured at a moment will have decayed to ``target``."""
    hours = hours_to_reach(nuclide, activity, target)
    return measured_at + dt.timedelta(hours=float(hours))


def after_half_lives(activity: Activity, count: Decimal | int) -> Activity:
    """What is left after a whole or part number of half lives."""
    lives = Decimal(count)
    if lives < 0:
        raise ValidationError("a count of half lives cannot be negative", count=str(lives))
    with localcontext() as ctx:
        ctx.prec = WORKING_PRECISION
        return activity.scaled(Decimal(2) ** (-lives))


def percent_remaining(nuclide: Nuclide, hours: Decimal) -> Decimal:
    """The decay factor as a percentage, to one decimal, for a printed table."""
    return (factor_over(nuclide, hours) * Decimal(100)).quantize(Decimal("0.1"))
