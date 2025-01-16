from decimal import Decimal

import pytest

from molycow.errors import ValidationError
from molycow.units import Activity


def test_a_millicurie_is_thirty_seven_megabecquerels() -> None:
    assert Activity.of(1, "mCi").mbq == Decimal("37.000000")
    assert Activity.of(37, "MBq").mci == Decimal("1.000000")


def test_the_becquerel_conversion_is_exact() -> None:
    assert Activity.of(1, "uCi").bq == Decimal("37000.000")


def test_parse_reads_what_an_order_sheet_writes() -> None:
    assert Activity.parse("25 mCi") == Activity.of(25, "mci")
    assert Activity.parse("925MBq") == Activity.of("925", "mbq")
    assert Activity.parse("  300 uCi ") == Activity.of(300, "uCi")


def test_the_micro_sign_is_accepted_both_ways() -> None:
    assert Activity.parse("300 µCi") == Activity.parse("300 uCi")
    assert Activity.parse("300 μCi") == Activity.parse("300 uCi")


def test_a_missing_unit_is_refused() -> None:
    with pytest.raises(ValidationError, match="should read like"):
        Activity.parse("25")


def test_an_unknown_unit_is_refused_by_name() -> None:
    with pytest.raises(ValidationError) as caught:
        Activity.parse("25 curies")
    assert caught.value.detail["unit"] == "curies"


def test_a_negative_activity_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative"):
        Activity.of(-1, "mCi")


def test_activity_rounds_to_the_nanocurie_on_the_way_in() -> None:
    assert Activity.of("1.00004", "uci").uci == Decimal("1.000")
    assert Activity.of("1.00050", "uci").uci == Decimal("1.001")


def test_addition_and_subtraction_stay_in_microcuries() -> None:
    total = Activity.of(10, "mCi") + Activity.of(500, "uCi")
    assert total.format() == "10.500 mCi"
    assert (total - Activity.of(500, "uci")).format() == "10.000 mCi"


def test_taking_more_than_is_there_is_refused() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Activity.of(1, "mCi") - Activity.of(2, "mCi")


def test_scaling_by_a_decay_factor() -> None:
    assert Activity.of(100, "mCi").scaled(Decimal("0.5")).format() == "50.000 mCi"
    assert Activity.of(100, "mCi").scaled(0.25).format() == "25.000 mCi"


def test_scaling_by_a_negative_factor_is_refused() -> None:
    with pytest.raises(ValidationError, match="negative factor"):
        Activity.of(1, "mCi").scaled(-1)


def test_a_ratio_is_a_plain_decimal() -> None:
    ratio = Activity.of(15, "uci").ratio_to(Activity.of(100, "mci"))
    assert ratio == Decimal("15") / Decimal("100000")


def test_a_ratio_against_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="zero activity"):
        Activity.of(1, "mCi").ratio_to(Activity.zero())


def test_activities_sort_and_compare() -> None:
    doses = [Activity.of(30, "mci"), Activity.of(1, "mci"), Activity.of(900, "uci")]
    assert [str(d) for d in sorted(doses)] == ["0.900 mCi", "1.000 mCi", "30.000 mCi"]
    assert Activity.zero().is_zero()


def test_format_picks_the_unit_and_the_places() -> None:
    dose = Activity.of("24.9994", "mci")
    assert dose.format("mci") == "24.999 mCi"
    assert dose.format("mci", places=1) == "25.0 mCi"
    assert dose.format("mbq", places=0) == "925 MBq"
    assert dose.format("gbq", places=4) == "0.9250 GBq"


def test_format_refuses_a_unit_it_does_not_know() -> None:
    with pytest.raises(ValidationError, match="unknown activity unit"):
        Activity.of(1, "mci").format("rutherford")


def test_a_word_where_a_number_belongs_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a number"):
        Activity.of("plenty", "mci")
    with pytest.raises(ValidationError, match="not a number"):
        Activity.of(None, "mci")
