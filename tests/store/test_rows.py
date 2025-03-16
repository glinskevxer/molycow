import datetime as dt
import sqlite3
from decimal import Decimal

import pytest

from molycow.clock import parse_moment, zone
from molycow.errors import ValidationError
from molycow.store.rows import (
    activity_in,
    activity_out,
    date_in,
    date_out,
    decimal_in,
    decimal_out,
    flag_in,
    flag_out,
    maybe_activity_in,
    maybe_date_in,
    maybe_moment_in,
    maybe_text_in,
    moment_in,
    moment_out,
    text_in,
    volume_in,
    volume_out,
)
from molycow.units import Activity, Volume


def a_row(**columns: object) -> sqlite3.Row:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    names = ", ".join(f"? AS {name}" for name in columns)
    row: sqlite3.Row = connection.execute(f"SELECT {names}", tuple(columns.values())).fetchone()
    connection.close()
    return row


def test_a_date_goes_out_and_comes_back() -> None:
    day = dt.date(2025, 4, 8)
    assert date_out(day) == "2025-04-08"
    assert date_in("2025-04-08", "opened_on") == day
    assert date_out(None) is None
    assert maybe_date_in(None, "closed_on") is None


def test_something_that_is_not_a_date_is_refused_by_column() -> None:
    with pytest.raises(ValidationError) as caught:
        date_in("last tuesday", "opened_on")
    assert caught.value.detail["column"] == "opened_on"
    with pytest.raises(ValidationError, match="does not hold a date"):
        date_in(4, "opened_on")


def test_a_moment_is_stored_in_utc() -> None:
    moment = parse_moment("2025-04-08 07:00", zone())
    assert moment_out(moment) == "2025-04-08T12:00:00+00:00"
    assert moment_in(moment_out(moment), "drawn_at") == moment


def test_a_naive_moment_cannot_be_stored() -> None:
    with pytest.raises(ValidationError, match="without a zone"):
        moment_out(dt.datetime(2025, 4, 8, 7, 0))  # noqa: DTZ001


def test_a_stored_moment_that_lost_its_zone_is_refused() -> None:
    with pytest.raises(ValidationError, match="lost its zone"):
        moment_in("2025-04-08T12:00:00", "drawn_at")
    with pytest.raises(ValidationError, match="does not hold a moment"):
        moment_in("noon", "drawn_at")
    assert maybe_moment_in(None, "drawn_at") is None


def test_stored_moments_sort_in_the_order_they_happened() -> None:
    tz = zone()
    first = moment_out(parse_moment("2025-11-02 01:30", tz))
    second = moment_out(parse_moment("2025-11-02 02:30", tz))
    assert first < second


def test_a_decimal_survives_the_round_trip_exactly() -> None:
    assert decimal_out(Decimal("6.0067")) == "6.0067"
    assert decimal_in("6.0067", "half_life") == Decimal("6.0067")
    with pytest.raises(ValidationError, match="does not hold a number"):
        decimal_in("about six", "half_life")


def test_an_activity_is_stored_in_microcuries() -> None:
    dose = Activity.of(25, "mCi")
    assert activity_out(dose) == "25000.000"
    assert activity_in("25000.000", "activity") == dose
    assert maybe_activity_in(None, "activity") is None


def test_a_volume_is_stored_in_millilitres() -> None:
    drawn = Volume.of("0.85")
    assert volume_out(drawn) == "0.850"
    assert volume_in("0.850", "volume") == drawn


def test_text_columns_are_checked_before_they_are_used() -> None:
    row = a_row(name="Saint Brannon", ended_on=None, count=4)
    assert text_in(row, "name") == "Saint Brannon"
    assert maybe_text_in(row, "ended_on") is None
    with pytest.raises(ValidationError, match="does not hold text"):
        text_in(row, "count")


def test_a_flag_is_a_zero_or_a_one() -> None:
    assert flag_out(True) == 1
    assert flag_out(False) == 0
    assert flag_in(1, "released") is True
    assert flag_in(0, "released") is False
    with pytest.raises(ValidationError, match="does not hold a flag"):
        flag_in("yes", "released")
