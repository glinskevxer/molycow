"""Times, and the local wall clock the pharmacy actually works to.

Everything stored is an aware datetime. Everything a technologist types is a
local wall clock time, because a calibration time written on a vial says
``0700`` and means seven in the morning in this building. The two are not the
same thing twice a year, so the conversion lives here and nowhere else.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from molycow.errors import ValidationError

DEFAULT_ZONE = "America/Chicago"

_DAY = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")
_CLOCK = re.compile(r"^\s*(\d{1,2}):?(\d{2})\s*$")


def zone(name: str = DEFAULT_ZONE) -> ZoneInfo:
    """The pharmacy's time zone, by name."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("unknown time zone", zone=name) from None


def parse_day(text: str) -> dt.date:
    """Read ``2025-03-04``."""
    match = _DAY.match(text)
    if match is None:
        raise ValidationError("a day should read like '2025-03-04'", text=text)
    year, month, day = (int(part) for part in match.groups())
    try:
        return dt.date(year, month, day)
    except ValueError as exc:
        raise ValidationError(f"that day is not on the calendar: {exc}", text=text) from None


def parse_clock(text: str) -> dt.time:
    """Read ``0700`` or ``7:30``, the way a vial label is written."""
    match = _CLOCK.match(text)
    if match is None:
        raise ValidationError("a time should read like '07:30' or '0730'", text=text)
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValidationError("that time is not on the clock", text=text)
    return dt.time(hour, minute)


def combine(day: dt.date, at: dt.time, tz: ZoneInfo) -> dt.datetime:
    """Put a local wall clock time on a day, and refuse the hour that does not exist.

    On the spring change the local clock jumps and there is no 2:30 that
    morning. On the autumn change 1:30 happens twice; the earlier one is the
    one meant, because that is the order the lab worked in.
    """
    naive = dt.datetime.combine(day, at)
    first = naive.replace(tzinfo=tz, fold=0)
    second = naive.replace(tzinfo=tz, fold=1)
    if first.utcoffset() != second.utcoffset() and first.astimezone(dt.UTC) > second.astimezone(
        dt.UTC
    ):
        raise ValidationError(
            "that local time does not exist on that day, the clocks moved",
            day=day.isoformat(),
            at=at.strftime("%H:%M"),
        )
    return first


def parse_moment(text: str, tz: ZoneInfo) -> dt.datetime:
    """Read ``2025-03-04 07:30`` or ``2025-03-04T07:30`` as a local wall clock time."""
    cleaned = text.strip().replace("T", " ")
    parts = cleaned.split()
    if len(parts) == 1:
        return combine(parse_day(parts[0]), dt.time(0, 0), tz)
    if len(parts) != 2:
        raise ValidationError("a moment should read like '2025-03-04 07:30'", text=text)
    return combine(parse_day(parts[0]), parse_clock(parts[1]), tz)


def elapsed(earlier: dt.datetime, later: dt.datetime) -> dt.timedelta:
    """Real elapsed time between two moments.

    Both sides go to UTC first. Subtracting two aware datetimes that carry the
    same tzinfo object ignores the offset, so an interval spanning a clock
    change comes out an hour wrong unless it is converted.
    """
    require_aware(earlier, "earlier")
    require_aware(later, "later")
    return later.astimezone(dt.UTC) - earlier.astimezone(dt.UTC)


def hours_between(earlier: dt.datetime, later: dt.datetime) -> Decimal:
    """Elapsed hours, signed, as a decimal so decay math can use it."""
    return Decimal(str(elapsed(earlier, later).total_seconds())) / Decimal(3600)


def minutes_between(earlier: dt.datetime, later: dt.datetime) -> Decimal:
    return Decimal(str(elapsed(earlier, later).total_seconds())) / Decimal(60)


def require_aware(moment: dt.datetime, what: str = "time") -> dt.datetime:
    """Refuse a naive datetime before it can be stored or compared."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValidationError(f"{what} has no time zone", value=moment.isoformat())
    return moment


def stamp(moment: dt.datetime, tz: ZoneInfo | None = None) -> str:
    """Print a moment in local time the way the hot lab sheet prints it."""
    require_aware(moment, "moment")
    local = moment.astimezone(tz) if tz is not None else moment
    return local.strftime("%Y-%m-%d %H:%M %Z")


def day_of(moment: dt.datetime, tz: ZoneInfo) -> dt.date:
    """The local calendar day a moment falls on."""
    return require_aware(moment).astimezone(tz).date()


class Clock(Protocol):
    """Where the current time comes from, so a test can hold it still."""

    def now(self) -> dt.datetime: ...


class SystemClock:
    """The real clock, in UTC."""

    def now(self) -> dt.datetime:
        return dt.datetime.now(tz=dt.UTC)


@dataclass
class FixedClock:
    """A clock that stays where it was put, and can be nudged forward."""

    moment: dt.datetime

    def __post_init__(self) -> None:
        require_aware(self.moment, "clock")

    def now(self) -> dt.datetime:
        return self.moment

    def advance(self, **delta: float) -> dt.datetime:
        self.moment = self.moment + dt.timedelta(**delta)
        return self.moment
