from decimal import Decimal

import pytest

from molycow.errors import ValidationError
from molycow.nuclides import (
    Use,
    daughters_of,
    fold_symbol,
    for_use,
    is_known,
    known,
    nuclide,
)


def test_the_workhorse_has_a_six_hour_half_life() -> None:
    tc = nuclide("Tc-99m")
    assert tc.half_life_hours == Decimal("6.0067")
    assert tc.element == "technetium"
    assert tc.principal_kev == Decimal("140.5")
    assert tc.parent == "Mo-99"


def test_a_symbol_is_folded_before_it_is_looked_up() -> None:
    for written in ("Tc-99m", "tc99m", "TC 99M", "tc_99m"):
        assert nuclide(written).symbol == "Tc-99m"
    assert fold_symbol("I-131") == "i131"


def test_a_nuclide_the_pharmacy_does_not_handle_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not handle"):
        nuclide("Pu-239")
    assert not is_known("Pu-239")
    assert is_known("f18")


def test_half_lives_answer_in_days_as_well() -> None:
    assert nuclide("I-131").half_life_days.quantize(Decimal("0.0001")) == Decimal("8.0252")
    assert nuclide("Lu-177").half_life_days == Decimal("6.647")


def test_a_short_lived_nuclide_is_used_the_shift_it_is_drawn() -> None:
    assert nuclide("F-18").is_short_lived
    assert nuclide("Tc-99m").is_short_lived
    assert not nuclide("I-131").is_short_lived
    assert not nuclide("Tl-201").is_short_lived


def test_every_row_is_reachable_by_its_own_symbol() -> None:
    for row in known():
        assert nuclide(row.symbol) is row


def test_no_two_rows_fold_to_the_same_key() -> None:
    keys = [row.key for row in known()]
    assert len(keys) == len(set(keys))


def test_the_table_is_split_by_what_it_is_for() -> None:
    assert nuclide("I-131").use is Use.THERAPEUTIC
    assert nuclide("Cs-137").use is Use.CHECK_SOURCE
    assert nuclide("Mo-99").use is Use.PARENT
    assert set(for_use(Use.CHECK_SOURCE)) == {
        nuclide("Cs-137"),
        nuclide("Co-57"),
        nuclide("Ba-133"),
    }


def test_the_generator_parent_knows_its_daughter() -> None:
    assert daughters_of("Mo-99") == (nuclide("Tc-99m"),)
    assert daughters_of("Ge-68") == (nuclide("Ga-68"),)
    assert daughters_of("I-131") == ()


def test_a_parent_that_is_not_in_the_table_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not handle"):
        daughters_of("Sr-82")


def test_every_half_life_is_positive_and_decimal() -> None:
    for row in known():
        assert isinstance(row.half_life_hours, Decimal)
        assert row.half_life_hours > 0


def test_a_nuclide_prints_as_its_symbol() -> None:
    assert str(nuclide("in111")) == "In-111"
