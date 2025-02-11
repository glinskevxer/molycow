from decimal import Decimal

import pytest

from molycow.clock import parse_moment, zone
from molycow.errors import ValidationError
from molycow.ingrowth import (
    BRANCHING,
    available,
    equilibrium_ratio,
    expectation,
    hours_to_maximum,
    ingrowth_factor,
    parent_after,
)
from molycow.units import Activity

TZ = zone()


def test_nothing_has_grown_in_the_instant_after_an_elution() -> None:
    assert ingrowth_factor(Decimal(0)) == 0
    assert available(Activity.of(2, "Ci"), Decimal(0)).is_zero()


def test_a_column_rested_overnight_gives_most_of_its_parent() -> None:
    factor = ingrowth_factor(Decimal(24))
    assert factor.quantize(Decimal("0.0001")) == Decimal("0.6902")


def test_the_daughter_peaks_just_short_of_a_day() -> None:
    peak = hours_to_maximum()
    assert peak.quantize(Decimal("0.01")) == Decimal("22.85")
    at_peak = ingrowth_factor(peak)
    assert at_peak > ingrowth_factor(peak - Decimal(2))
    assert at_peak > ingrowth_factor(peak + Decimal(2))


def test_the_ratio_a_rested_column_settles_at() -> None:
    assert equilibrium_ratio().quantize(Decimal("0.0001")) == Decimal("0.9661")
    assert ingrowth_factor(Decimal(96)) < equilibrium_ratio()


def test_the_branching_fraction_caps_what_can_ever_appear() -> None:
    for hours in (Decimal(6), Decimal(24), Decimal(72), Decimal(240)):
        assert ingrowth_factor(hours) < BRANCHING * Decimal("1.05")


def test_ingrowth_does_not_run_backwards() -> None:
    with pytest.raises(ValidationError, match="does not run backwards"):
        ingrowth_factor(Decimal(-1))


def test_residual_technetium_decays_underneath_the_ingrowth() -> None:
    parent = Activity.of("1.4", "Ci")
    clean = available(parent, Decimal(24))
    dirty = available(parent, Decimal(24), Activity.of(100, "mCi"))
    assert dirty > clean
    assert (dirty - clean).format() == "6.269 mCi"


def test_the_parent_decays_on_its_own_schedule() -> None:
    assert parent_after(Activity.of(1, "Ci"), Decimal("65.976")).format("ci", 4) == "0.5000 Ci"


def test_an_expectation_carries_both_sides_of_the_column() -> None:
    milked = parse_moment("2025-05-06 06:30", TZ)
    again = parse_moment("2025-05-07 06:30", TZ)
    exp = expectation(Activity.of("1.75", "Ci"), milked, again)
    assert exp.hours_rested == Decimal(24)
    assert exp.expected.format("mci", 1) == "1207.8 mCi"
    assert exp.parent_now.format("mci", 1) == "1360.0 mCi"


def test_efficiency_is_what_came_off_against_what_was_there() -> None:
    milked = parse_moment("2025-05-06 06:30", TZ)
    again = parse_moment("2025-05-07 06:30", TZ)
    exp = expectation(Activity.of("1.75", "Ci"), milked, again)
    got = exp.expected.scaled(Decimal("0.9"))
    assert exp.efficiency(got).quantize(Decimal("0.001")) == Decimal("0.900")


def test_efficiency_against_an_empty_column_is_refused() -> None:
    milked = parse_moment("2025-05-06 06:30", TZ)
    exp = expectation(Activity.zero(), milked, milked)
    with pytest.raises(ValidationError, match="nothing was expected"):
        exp.efficiency(Activity.of(1, "mci"))


def test_a_column_cannot_be_milked_before_it_was_last_milked() -> None:
    milked = parse_moment("2025-05-06 06:30", TZ)
    earlier = parse_moment("2025-05-05 06:30", TZ)
    with pytest.raises(ValidationError, match="before it was last milked"):
        expectation(Activity.of(1, "Ci"), milked, earlier)


def test_a_second_milking_the_same_afternoon_gives_much_less() -> None:
    yesterday = parse_moment("2025-05-06 06:30", TZ)
    morning = parse_moment("2025-05-07 06:30", TZ)
    afternoon = parse_moment("2025-05-07 14:30", TZ)
    parent = Activity.of("1.75", "Ci")
    overnight = expectation(parent, yesterday, morning)
    same_day = expectation(overnight.parent_now, morning, afternoon)
    assert same_day.expected < overnight.expected
    assert same_day.expected.format("mci", 0) == "686 mCi"
