"""The badge readings, and who has to be spoken to about them.

The readings come back from the service quarterly, months after the work that
produced them. The point of keeping them here is the yearly total: nobody
notices a quarter creeping up, and everybody notices a year that has run out.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import ConflictError
from molycow.model.badge import Badge, YearToDate, quarter_of
from molycow.store.badges import BadgeRepository
from molycow.store.book import Book


@dataclass(frozen=True)
class Watch:
    """A person whose year is worth a word."""

    year_to_date: YearToDate
    reason: str

    def line(self) -> str:
        """The line the safety officer reads."""
        return f"{self.year_to_date.line()}  {self.reason}"


class DosimetryService:
    """The badge file."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._badges = BadgeRepository(book)

    def record(
        self,
        person: str,
        period: str,
        deep_mrem: Decimal,
        extremity_mrem: Decimal,
        read_on: dt.date,
    ) -> Badge:
        """Write one badge reading down."""
        if self._badges.find(person, period) is not None:
            raise ConflictError(
                "that badge period has already been read", person=person, period=period
            )
        badge = Badge(
            person=person,
            period=period,
            deep_mrem=deep_mrem,
            extremity_mrem=extremity_mrem,
            read_on=read_on,
        )
        return self._badges.add(badge)

    def quarter(self, period: str) -> list[Badge]:
        return self._badges.for_period(period)

    def year_to_date(self, person: str, year: int) -> YearToDate:
        return self._badges.year_to_date(person, year)

    def watch_list(self, year: int) -> list[Watch]:
        """Everybody over the investigation level or over the limit, worst first."""
        found: list[Watch] = []
        for person in self._badges.people():
            so_far = self._badges.year_to_date(person, year)
            if not so_far.badges:
                continue
            if so_far.over_limit:
                found.append(Watch(so_far, "over the yearly limit"))
            elif any(one.over_investigation_level for one in so_far.badges):
                found.append(Watch(so_far, "a quarter over the investigation level"))
        return sorted(found, key=lambda one: one.year_to_date.deep, reverse=True)

    def missing(self, period: str) -> list[str]:
        """Everybody with badges on file who has no reading for a quarter."""
        read = {one.person for one in self._badges.for_period(period)}
        return [one for one in self._badges.people() if one not in read]

    def period_for(self, day: dt.date) -> str:
        return quarter_of(day)
