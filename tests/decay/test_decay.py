import datetime as dt
from decimal import Decimal

import pytest

from molycow.clock import parse_moment, zone
from molycow.decay import (
    after_half_lives,
    decay_between,
    decay_over,
    factor_between,
    factor_over,
    half_lives_over,
    hours_to_reach,
    moment_reaching,
    needed_at,
    percent_remaining,
)
from molycow.errors import ValidationError
from molycow.nuclides import nuclide
from molycow.units import Activity

TC = nuclide("Tc-99m")
I131 = nuclide("I-131")
TZ = zone()


def q(value: Decimal, places: str = "0.000001") -> Decimal:
    return value.quantize(Decimal(places))


def test_one_half_life_leaves_half() -> None:
    assert q(factor_over(TC, TC.half_life_hours)) == Decimal("0.500000")
    assert q(factor_over(TC, TC.half_life_hours * 2)) == Decimal("0.250000")


def test_the_decay_constant_matches_the_half_life() -> None:
    from molycow.decay import decay_constant

    assert q(decay_constant(TC) * TC.half_life_hours, "0.00000001") == Decimal("0.69314718")


def test_a_negative_interval_reads_backwards() -> None:
    assert q(factor_over(TC, -TC.half_life_hours)) == Decimal("2.000000")


def test_half_lives_over_counts_the_interval() -> None:
    assert q(half_lives_over(TC, Decimal("12.0134"))) == Decimal("2.000000")


def test_a_technetium_dose_left_overnight_is_gone_in_the_morning() -> None:
    drawn = Activity.of(30, "mCi")
    assert decay_over(drawn, TC, Decimal(16)).format() == "4.734 mCi"


def test_carrying_an_activity_between_two_moments() -> None:
    calibrated = parse_moment("2025-04-08 07:00", TZ)
    scanned = parse_moment("2025-04-08 13:00", TZ)
    vial = Activity.of(100, "mCi")
    assert decay_between(vial, TC, calibrated, scanned).format() == "50.039 mCi"
    assert q(factor_between(TC, calibrated, scanned), "0.0001") == Decimal("0.5004")


def test_drawing_early_means_drawing_more() -> None:
    wanted = Activity.of(20, "mCi")
    at_scan = parse_moment("2025-04-08 13:00", TZ)
    drawn = parse_moment("2025-04-08 07:00", TZ)
    syringe = needed_at(wanted, TC, wanted_at=at_scan, drawn_at=drawn)
    assert syringe.format() == "39.969 mCi"
    assert decay_between(syringe, TC, drawn, at_scan).format() == "20.000 mCi"


def test_drawing_at_the_calibration_time_changes_nothing() -> None:
    moment = parse_moment("2025-04-08 07:00", TZ)
    wanted = Activity.of(20, "mCi")
    assert needed_at(wanted, TC, moment, moment) == wanted


def test_how_long_until_a_vial_falls_to_a_target() -> None:
    hours = hours_to_reach(TC, Activity.of(100, "mCi"), Activity.of(25, "mCi"))
    assert q(hours, "0.0001") == Decimal("12.0134")


def test_a_target_above_the_activity_is_refused() -> None:
    with pytest.raises(ValidationError, match="above the activity"):
        hours_to_reach(TC, Activity.of(10, "mCi"), Activity.of(20, "mCi"))


def test_zero_is_not_a_target_and_zero_is_not_a_start() -> None:
    with pytest.raises(ValidationError, match="never reaches exactly zero"):
        hours_to_reach(TC, Activity.of(10, "mCi"), Activity.zero())
    with pytest.raises(ValidationError, match="from zero activity"):
        hours_to_reach(TC, Activity.zero(), Activity.of(1, "uci"))


def test_the_moment_a_waste_vial_reaches_background() -> None:
    measured = parse_moment("2025-04-08 07:00", TZ)
    when = moment_reaching(I131, Activity.of(5, "mCi"), measured, Activity.of(5, "uci"))
    assert when - measured > dt.timedelta(days=79)
    assert when - measured < dt.timedelta(days=81)


def test_whole_half_lives_are_easy_to_ask_for() -> None:
    assert after_half_lives(Activity.of(80, "mCi"), 3).format() == "10.000 mCi"
    assert after_half_lives(Activity.of(80, "mCi"), Decimal("0.5")).format() == "56.569 mCi"


def test_a_negative_count_of_half_lives_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        after_half_lives(Activity.of(1, "mCi"), -1)


def test_a_printed_decay_table_is_one_decimal_of_a_percent() -> None:
    assert percent_remaining(TC, Decimal(1)) == Decimal("89.1")
    assert percent_remaining(TC, Decimal(6)) == Decimal("50.0")
    assert percent_remaining(I131, Decimal(24)) == Decimal("91.7")


def test_ten_half_lives_is_a_thousandth() -> None:
    left = after_half_lives(Activity.of(1000, "mCi"), 10)
    assert left.format("mci", 4) == "0.9766 mCi"
