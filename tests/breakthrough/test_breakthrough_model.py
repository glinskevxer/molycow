from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.breakthrough import (
    ALUMINIUM_LIMIT,
    MOLY_LIMIT,
    Breakthrough,
    hours_until_limit,
    ratio_at,
    ratio_growth_per_hour,
)
from molycow.units import Activity

TESTED = at("2025-04-08 06:45")


def a_test(**changed: object) -> Breakthrough:
    fields: dict[str, object] = {
        "elution_id": "EL-250408-01",
        "tested_at": TESTED,
        "moly": Activity.of("0.9", "uci"),
        "technetium": Activity.of(940, "mci"),
        "aluminium_ppm": Decimal("4"),
        "tested_by": "K. Ruzicka",
    }
    fields.update(changed)
    return Breakthrough(**fields)  # type: ignore[arg-type]


def test_the_limits_are_the_ones_in_the_manual() -> None:
    assert Decimal("0.15") == MOLY_LIMIT
    assert Decimal("10") == ALUMINIUM_LIMIT


def test_the_ratio_is_microcuries_of_parent_per_millicurie_of_daughter() -> None:
    assert a_test().ratio.quantize(Decimal("0.0001")) == Decimal("0.0010")


def test_a_clean_vial_passes_both_tests() -> None:
    clean = a_test()
    assert clean.moly_passes
    assert clean.aluminium_passes
    assert clean.passes
    assert clean.failure() is None


def test_molybdenum_over_the_limit_fails_by_name() -> None:
    dirty = a_test(moly=Activity.of(200, "uci"))
    assert not dirty.moly_passes
    assert not dirty.passes
    assert dirty.failure() == "molybdenum breakthrough over the limit"


def test_aluminium_over_the_limit_fails_by_name() -> None:
    dirty = a_test(aluminium_ppm=Decimal("12"))
    assert dirty.moly_passes
    assert not dirty.aluminium_passes
    assert dirty.failure() == "aluminium over the limit"


def test_aluminium_right_on_the_limit_passes() -> None:
    assert a_test(aluminium_ppm=ALUMINIUM_LIMIT).aluminium_passes


def test_the_ratio_climbs_because_the_daughter_decays_faster() -> None:
    assert ratio_growth_per_hour() > 0
    start = Decimal("0.01")
    assert ratio_at(start, Decimal(6)) > start
    assert ratio_at(start, Decimal(0)) == start


def test_the_ratio_at_a_later_moment_is_read_off_the_test() -> None:
    reading = a_test(moly=Activity.of(30, "uci"))
    assert reading.ratio.quantize(Decimal("0.0001")) == Decimal("0.0319")
    later = reading.ratio_at(at("2025-04-08 18:45"))
    assert later > reading.ratio


def test_the_ratio_cannot_be_read_before_the_test() -> None:
    with pytest.raises(ValidationError, match="before the test"):
        a_test().ratio_at(at("2025-04-08 06:00"))


def test_a_vial_that_is_already_over_has_no_time_left() -> None:
    assert hours_until_limit(Decimal("0.2")) == 0
    assert a_test(moly=Activity.of(200, "uci")).usable_until == TESTED


def test_a_ratio_that_is_not_a_ratio_cannot_be_projected() -> None:
    with pytest.raises(ValidationError, match="above zero"):
        hours_until_limit(Decimal(0))


def test_a_dirty_vial_runs_out_before_the_twelve_hour_shelf_life() -> None:
    reading = a_test(moly=Activity.of(80, "uci"))
    hours = hours_until_limit(reading.ratio)
    assert Decimal(0) < hours < Decimal(12)
    assert reading.is_usable_at(at("2025-04-08 09:00"))
    assert not reading.is_usable_at(at("2025-04-08 18:00"))


def test_a_clean_vial_outlasts_the_shelf_life() -> None:
    clean = a_test()
    assert hours_until_limit(clean.ratio) > Decimal(24)
    assert clean.is_usable_at(at("2025-04-08 18:30"))


def test_aluminium_failing_makes_the_vial_unusable_whatever_the_clock_says() -> None:
    assert not a_test(aluminium_ppm=Decimal("11")).is_usable_at(TESTED)


def test_a_test_needs_a_technetium_reading_and_a_signature() -> None:
    with pytest.raises(ValidationError, match="measured against"):
        a_test(technetium=Activity.zero())
    with pytest.raises(ValidationError, match="signed by"):
        a_test(tested_by="  ")
    with pytest.raises(ValidationError, match="cannot be negative"):
        a_test(aluminium_ppm=Decimal("-1"))


def test_a_test_belongs_to_an_elution() -> None:
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_test(elution_id="GEN-0027")
