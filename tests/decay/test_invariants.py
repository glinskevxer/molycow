"""Properties the arithmetic has to hold whatever numbers it is given.

These are swept rather than sampled: the same list of nuclides and intervals
every run, because a physics test that passes four times out of five is worse
than no test at all. What they are looking for is the class of mistake that a
worked example does not catch, like an inverse that is only an inverse near
the middle of the range.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from molycow.clock import parse_moment, zone
from molycow.decay import (
    after_half_lives,
    decay_between,
    decay_over,
    factor_over,
    hours_to_reach,
    needed_at,
)
from molycow.ingrowth import available, ingrowth_factor, parent_after
from molycow.nuclides import Use, known, nuclide
from molycow.units import Activity, Concentration, Volume

TZ = zone()

HOURS = (
    Decimal("0.25"),
    Decimal(1),
    Decimal(6),
    Decimal(24),
    Decimal(72),
    Decimal(240),
)

WORKING = [one for one in known() if one.use is not Use.CHECK_SOURCE]


@pytest.mark.parametrize("symbol", [one.symbol for one in WORKING])
def test_every_nuclide_loses_half_in_one_half_life(symbol: str) -> None:
    found = nuclide(symbol)
    left = decay_over(Activity.of(100, "mci"), found, found.half_life_hours)
    assert left.format("mci", 2) == "50.00 mCi"


@pytest.mark.parametrize("symbol", [one.symbol for one in WORKING])
def test_decay_never_grows_an_activity_forwards(symbol: str) -> None:
    found = nuclide(symbol)
    start = Activity.of(500, "mci")
    for hours in HOURS:
        assert decay_over(start, found, hours) <= start


@pytest.mark.parametrize("symbol", [one.symbol for one in WORKING])
def test_carrying_forward_and_back_returns_what_was_there(symbol: str) -> None:
    """Within the range a vial is actually carried across.

    Activity is rounded to the nanocurie on the way in. Past a few half lives
    that rounding is most of what is left, so carrying back does not undo it,
    and the test would be measuring the rounding rather than the decay.
    """
    found = nuclide(symbol)
    start = Activity.of(250, "mci")
    for hours in HOURS:
        if hours > found.half_life_hours * Decimal(3):
            continue
        there = decay_over(start, found, hours)
        back = decay_over(there, found, -hours)
        assert abs(back.uci - start.uci) < Decimal("0.05")


@pytest.mark.parametrize("symbol", [one.symbol for one in WORKING])
def test_what_is_needed_now_decays_to_what_was_wanted(symbol: str) -> None:
    """Only over intervals a dose is really drawn across.

    Three half lives back is already a syringe eight times the label. Past
    that the number carried backwards is so large that the microcurie the
    activity is rounded to no longer divides into it evenly, which is a fact
    about the rounding rather than about the decay.
    """
    found = nuclide(symbol)
    wanted = Activity.of(22, "mci")
    drawn = parse_moment("2025-04-08 07:40", TZ)
    for hours in HOURS:
        if hours > found.half_life_hours * Decimal(3):
            continue
        at_scan = drawn + dt.timedelta(hours=float(hours))
        syringe = needed_at(wanted, found, at_scan, drawn)
        assert decay_between(syringe, found, drawn, at_scan).format("mci", 1) == "22.0 mCi"


@pytest.mark.parametrize("symbol", [one.symbol for one in WORKING])
def test_the_time_to_reach_a_target_reaches_it(symbol: str) -> None:
    found = nuclide(symbol)
    start = Activity.of(400, "mci")
    for share in ("0.5", "0.1", "0.01"):
        target = start.scaled(share)
        hours = hours_to_reach(found, start, target)
        assert decay_over(start, found, hours).format("mci", 2) == target.format("mci", 2)


def test_half_lives_and_hours_agree_with_each_other() -> None:
    for one in WORKING:
        for count in (1, 2, 5, 10):
            by_hours = decay_over(
                Activity.of(1000, "mci"), one, one.half_life_hours * Decimal(count)
            )
            by_lives = after_half_lives(Activity.of(1000, "mci"), count)
            assert abs(by_hours.uci - by_lives.uci) < Decimal("0.05")


def test_a_decay_factor_stays_between_nothing_and_everything() -> None:
    for one in WORKING:
        for hours in HOURS:
            factor = factor_over(one, hours)
            assert Decimal(0) < factor <= Decimal(1)


def test_the_column_never_gives_up_more_than_the_parent_it_had() -> None:
    parent = Activity.of(2, "Ci")
    for hours in HOURS:
        grown = available(parent, hours)
        assert grown < parent
        assert grown < parent_after(parent, Decimal(0))


def test_ingrowth_rises_then_falls_around_its_peak() -> None:
    rising = [ingrowth_factor(Decimal(hours)) for hours in (2, 6, 12, 18, 22)]
    assert rising == sorted(rising)
    falling = [ingrowth_factor(Decimal(hours)) for hours in (24, 36, 48, 96)]
    assert falling == sorted(falling, reverse=True)


def test_a_concentration_answers_the_question_it_was_built_from() -> None:
    """The volume it gives back holds the activity that was asked for.

    Only to within the microlitre the volume is rounded to. Out of a vial at
    600 mCi/mL, twenty two millicuries is thirty seven microlitres, and the
    last of those microlitres is worth half a millicurie. That is a fact about
    syringes, not about the arithmetic.
    """
    wanted = Activity.of(22, "mci")
    for millilitres in ("0.5", "1", "3.5", "10"):
        volume = Volume.of(millilitres)
        concentration = Concentration.of(Activity.of(300, "mci"), volume)
        assert concentration.activity_in(volume).format("mci", 1) == "300.0 mCi"
        drawn = concentration.volume_for(wanted)
        held = concentration.activity_in(drawn)
        assert abs(held.uci - wanted.uci) < concentration.uci_per_ml / Decimal(1000)


def test_activity_arithmetic_round_trips_through_every_unit() -> None:
    start = Activity.of("37.5", "mci")
    for unit in ("uci", "mci", "ci", "kbq", "mbq", "gbq"):
        text = start.format(unit, places=6)
        assert Activity.parse(text).format("mci", 3) == "37.500 mCi"
    assert Activity.parse(start.format("bq", places=0)).format("mci", 3) == "37.500 mCi"
