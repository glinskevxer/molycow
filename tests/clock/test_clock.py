import datetime as dt
from decimal import Decimal

import pytest

from molycow.clock import (
    DEFAULT_ZONE,
    FixedClock,
    SystemClock,
    combine,
    day_of,
    elapsed,
    hours_between,
    minutes_between,
    parse_clock,
    parse_day,
    parse_moment,
    require_aware,
    stamp,
    zone,
)
from molycow.errors import ValidationError


def test_the_default_zone_is_the_pharmacy_zone() -> None:
    assert DEFAULT_ZONE == "America/Chicago"
    assert zone().key == "America/Chicago"


def test_an_unknown_zone_is_refused() -> None:
    with pytest.raises(ValidationError, match="unknown time zone"):
        zone("Mars/Olympus")


def test_a_day_is_read_from_an_iso_date() -> None:
    assert parse_day("2025-03-04") == dt.date(2025, 3, 4)
    assert parse_day("  2025-03-04 ") == dt.date(2025, 3, 4)


def test_a_day_off_the_calendar_is_refused() -> None:
    with pytest.raises(ValidationError, match="not on the calendar"):
        parse_day("2025-02-30")
    with pytest.raises(ValidationError, match="should read like"):
        parse_day("4 March 2025")


def test_a_clock_time_reads_with_or_without_the_colon() -> None:
    assert parse_clock("0730") == dt.time(7, 30)
    assert parse_clock("7:30") == dt.time(7, 30)
    assert parse_clock("23:59") == dt.time(23, 59)


def test_a_time_off_the_clock_is_refused() -> None:
    with pytest.raises(ValidationError, match="not on the clock"):
        parse_clock("25:00")
    with pytest.raises(ValidationError, match="should read like"):
        parse_clock("half seven")


def test_a_moment_is_local_wall_clock_time() -> None:
    tz = zone()
    moment = parse_moment("2025-03-04 07:30", tz)
    assert moment.utcoffset() == dt.timedelta(hours=-6)
    assert stamp(moment) == "2025-03-04 07:30 CST"


def test_a_bare_day_is_midnight_that_morning() -> None:
    tz = zone()
    assert parse_moment("2025-03-04", tz) == combine(dt.date(2025, 3, 4), dt.time(0, 0), tz)


def test_the_hour_the_clocks_skip_does_not_exist() -> None:
    tz = zone()
    with pytest.raises(ValidationError, match="clocks moved"):
        parse_moment("2025-03-09 02:30", tz)


def test_the_hour_the_clocks_repeat_takes_the_earlier_one() -> None:
    tz = zone()
    moment = parse_moment("2025-11-02 01:30", tz)
    assert moment.utcoffset() == dt.timedelta(hours=-5)


def test_a_moment_that_is_not_a_moment_is_refused() -> None:
    with pytest.raises(ValidationError, match="should read like"):
        parse_moment("2025-03-04 07:30 sharp", zone())


def test_elapsed_hours_are_decimal_and_signed() -> None:
    tz = zone()
    start = parse_moment("2025-03-04 07:00", tz)
    end = parse_moment("2025-03-04 13:30", tz)
    assert hours_between(start, end) == Decimal("6.5")
    assert hours_between(end, start) == Decimal("-6.5")
    assert minutes_between(start, end) == Decimal("390")


def test_elapsed_hours_cross_the_spring_change_in_real_time() -> None:
    tz = zone()
    start = parse_moment("2025-03-09 01:00", tz)
    end = parse_moment("2025-03-09 04:00", tz)
    assert start.utcoffset() != end.utcoffset()
    assert hours_between(start, end) == Decimal("2")
    assert elapsed(start, end) == dt.timedelta(hours=2)


def test_a_naive_time_is_refused_before_it_can_be_compared() -> None:
    naive = dt.datetime(2025, 3, 4, 7, 30)  # noqa: DTZ001
    with pytest.raises(ValidationError, match="no time zone"):
        require_aware(naive)
    with pytest.raises(ValidationError, match="no time zone"):
        hours_between(naive, dt.datetime.now(tz=dt.UTC))


def test_a_moment_belongs_to_the_local_day_not_the_utc_one() -> None:
    tz = zone()
    late = parse_moment("2025-06-30 23:30", tz)
    assert late.astimezone(dt.UTC).date() == dt.date(2025, 7, 1)
    assert day_of(late, tz) == dt.date(2025, 6, 30)


def test_stamp_can_be_asked_for_another_zone() -> None:
    moment = parse_moment("2025-06-30 23:30", zone())
    assert stamp(moment, zone("UTC")) == "2025-07-01 04:30 UTC"


def test_the_system_clock_is_aware_and_moves() -> None:
    now = SystemClock().now()
    assert now.tzinfo is dt.UTC


def test_a_fixed_clock_stays_put_until_it_is_advanced() -> None:
    clock = FixedClock(parse_moment("2025-03-04 07:00", zone()))
    first = clock.now()
    assert clock.now() == first
    clock.advance(hours=6)
    assert hours_between(first, clock.now()) == Decimal("6")


def test_a_fixed_clock_refuses_a_naive_start() -> None:
    with pytest.raises(ValidationError, match="no time zone"):
        FixedClock(dt.datetime(2025, 3, 4, 7, 0))  # noqa: DTZ001
