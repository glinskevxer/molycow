import datetime as dt

import pytest

from molycow.errors import ValidationError
from molycow.ids import Identifier, Kind, expect, make, next_serial, normalise, parse

DAY = dt.date(2025, 4, 8)


def test_a_durable_number_is_a_flat_serial() -> None:
    assert make(Kind.CUSTOMER, 142) == "CU-0142"
    assert make(Kind.INSTRUMENT, 3) == "IC-0003"
    assert make(Kind.GENERATOR, 27) == "GEN-0027"


def test_a_daily_number_carries_the_day_it_belongs_to() -> None:
    assert make(Kind.ELUTION, 3, DAY) == "EL-250408-03"
    assert make(Kind.DOSE, 41, DAY) == "DS-250408-41"
    assert make(Kind.BATCH, 2, DAY) == "B-250408-02"


def test_a_daily_number_without_a_day_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs the day"):
        make(Kind.ELUTION, 3)


def test_a_durable_number_with_a_day_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not carry a day"):
        make(Kind.CUSTOMER, 3, DAY)


def test_serials_start_at_one() -> None:
    with pytest.raises(ValidationError, match="starts at one"):
        make(Kind.DOSE, 0, DAY)


def test_a_serial_can_run_out() -> None:
    with pytest.raises(ValidationError, match="run out"):
        make(Kind.DOSE, 1000, DAY)
    with pytest.raises(ValidationError, match="run out"):
        make(Kind.CUSTOMER, 1000000)


def test_parsing_gives_back_what_was_made() -> None:
    for text in ("CU-0142", "EL-250408-03", "DS-250408-41", "GEN-0027"):
        assert str(parse(text)) == text


def test_parsing_reads_the_day_out_of_the_middle() -> None:
    found = parse("EL-250408-03")
    assert found.kind is Kind.ELUTION
    assert found.serial == 3
    assert found.day == DAY


def test_a_number_is_normalised_before_it_is_read() -> None:
    assert normalise(" el-250408-03 ") == "EL-250408-03"
    assert parse(" cu-142 ") == Identifier(Kind.CUSTOMER, 142)


def test_a_daily_number_written_flat_is_refused() -> None:
    with pytest.raises(ValidationError, match="missing its day"):
        parse("EL-0003")


def test_a_durable_number_written_with_a_day_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not carry a day"):
        parse("CU-250408-03")


def test_an_unknown_prefix_is_refused_by_name() -> None:
    with pytest.raises(ValidationError) as caught:
        parse("ZZ-0004")
    assert caught.value.detail["prefix"] == "ZZ"


def test_a_day_that_is_not_a_day_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a day"):
        parse("EL-250230-03")


def test_something_that_is_not_a_number_at_all_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a label number"):
        parse("the red one")


def test_expect_refuses_the_wrong_kind_and_says_both() -> None:
    with pytest.raises(ValidationError) as caught:
        expect("CU-0142", Kind.INSTRUMENT)
    assert caught.value.detail["wanted"] == "IC"
    assert caught.value.detail["got"] == "CU"
    assert expect("CU-0142", Kind.CUSTOMER).serial == 142


def test_the_next_daily_serial_restarts_each_morning() -> None:
    issued = ["EL-250407-01", "EL-250407-02", "EL-250408-01"]
    assert next_serial(issued, Kind.ELUTION, DAY) == 2
    assert next_serial(issued, Kind.ELUTION, dt.date(2025, 4, 9)) == 1


def test_the_next_flat_serial_carries_on() -> None:
    assert next_serial(["CU-0007", "CU-0011", "IC-0004"], Kind.CUSTOMER) == 12
    assert next_serial([], Kind.CUSTOMER) == 1


def test_the_next_serial_ignores_the_other_kinds() -> None:
    issued = ["DS-250408-09", "EL-250408-01"]
    assert next_serial(issued, Kind.DOSE, DAY) == 10


def test_which_kinds_restart_daily() -> None:
    assert Kind.ELUTION.is_daily
    assert Kind.DOSE.is_daily
    assert not Kind.CUSTOMER.is_daily
    assert not Kind.KIT_LOT.is_daily
