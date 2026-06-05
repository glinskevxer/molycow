"""Reading and writing the badge readings."""

from __future__ import annotations

import sqlite3

from molycow.model.badge import Badge, YearToDate
from molycow.store.records import Records
from molycow.store.rows import date_in, date_out, decimal_in, decimal_out, text_in


def badge_from(row: sqlite3.Row) -> Badge:
    """Build a badge reading out of a row of the table."""
    return Badge(
        person=text_in(row, "person"),
        period=text_in(row, "period"),
        deep_mrem=decimal_in(row["deep_mrem"], "deep_mrem"),
        extremity_mrem=decimal_in(row["extremity_mrem"], "extremity_mrem"),
        read_on=date_in(row["read_on"], "read_on"),
    )


class BadgeRepository(Records):
    """Every badge reading the service has sent back."""

    def add(self, badge: Badge) -> Badge:
        self._book.execute(
            """
            INSERT INTO badge_reading
              (person, period, deep_mrem, extremity_mrem, read_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                badge.person,
                badge.period,
                decimal_out(badge.deep_mrem),
                decimal_out(badge.extremity_mrem),
                date_out(badge.read_on),
            ),
        )
        return badge

    def find(self, person: str, period: str) -> Badge | None:
        row = self._book.one(
            "SELECT * FROM badge_reading WHERE person = ? AND period = ?", (person, period)
        )
        return None if row is None else badge_from(row)

    def get(self, person: str, period: str) -> Badge:
        """One reading, or a refusal if that badge has not come back."""
        return self.required(
            self.find(person, period),
            "no badge reading for that person and period",
            person=person,
            period=period,
        )

    def all(self) -> list[Badge]:
        rows = self._book.all("SELECT * FROM badge_reading ORDER BY period, person")
        return [badge_from(row) for row in rows]

    def for_period(self, period: str) -> list[Badge]:
        """Everybody's badge for one quarter."""
        rows = self._book.all(
            "SELECT * FROM badge_reading WHERE period = ? ORDER BY person", (period,)
        )
        return [badge_from(row) for row in rows]

    def for_person(self, person: str) -> list[Badge]:
        """One person's badges, oldest first."""
        rows = self._book.all(
            "SELECT * FROM badge_reading WHERE person = ? ORDER BY period", (person,)
        )
        return [badge_from(row) for row in rows]

    def year_to_date(self, person: str, year: int) -> YearToDate:
        """One person's year so far."""
        badges = [one for one in self.for_person(person) if one.year == year]
        return YearToDate(person=person, year=year, badges=tuple(badges))

    def people(self) -> list[str]:
        """Everybody with a badge in the book."""
        rows = self._book.all("SELECT DISTINCT person FROM badge_reading ORDER BY person")
        return [str(row["person"]) for row in rows]
