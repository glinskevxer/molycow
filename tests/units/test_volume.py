from decimal import Decimal

import pytest

from molycow.errors import ValidationError
from molycow.units import Activity, Concentration, Volume


def test_a_volume_is_kept_to_the_microlitre() -> None:
    assert Volume.of("1.00049").ml == Decimal("1.000")
    assert Volume.of("1.0005").ml == Decimal("1.001")


def test_parse_takes_millilitres_and_microlitres() -> None:
    assert Volume.parse("2.5 mL") == Volume.of("2.5")
    assert Volume.parse("2.5cc") == Volume.of("2.5")
    assert Volume.parse("250 uL") == Volume.of("0.25")
    assert Volume.parse("6") == Volume.of(6)


def test_parse_refuses_a_unit_that_is_not_a_volume() -> None:
    with pytest.raises(ValidationError, match="unknown volume unit"):
        Volume.parse("3 mCi")


def test_a_negative_volume_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        Volume.of("-0.4")


def test_volumes_add_and_subtract() -> None:
    assert str(Volume.of("3.2") + Volume.of("0.8")) == "4.000 mL"
    assert str(Volume.of("3.2") - Volume.of("0.2")) == "3.000 mL"


def test_drawing_more_than_the_vial_holds_is_refused() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Volume.of(1) - Volume.of(2)


def test_a_volume_can_be_scaled_by_a_factor() -> None:
    assert str(Volume.of(10).scaled("0.5")) == "5.000 mL"
    with pytest.raises(ValidationError, match="negative factor"):
        Volume.of(10).scaled(-2)


def test_a_concentration_answers_both_directions() -> None:
    conc = Concentration.of(Activity.of(100, "mci"), Volume.of(10))
    assert conc.format() == "10.000 mCi/mL"
    assert str(conc.volume_for(Activity.of(25, "mci"))) == "2.500 mL"
    assert conc.activity_in(Volume.of("0.5")).format() == "5.000 mCi"


def test_a_concentration_needs_a_volume_to_sit_in() -> None:
    with pytest.raises(ValidationError, match="zero volume"):
        Concentration.of(Activity.of(1, "mci"), Volume.zero())


def test_a_concentration_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="positive"):
        Concentration(Decimal(0))


def test_a_vial_that_is_all_saline_reads_as_zero_activity() -> None:
    conc = Concentration.of(Activity.of(1, "uci"), Volume.of(10))
    assert conc.activity_in(Volume.of("0.001")).is_zero()


def test_a_volume_pads_in_an_f_string() -> None:
    assert f"{Volume.of('0.55'):>9}" == " 0.550 mL"
