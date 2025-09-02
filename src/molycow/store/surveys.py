"""Reading and writing the survey book."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import NotFoundError
from molycow.ids import Kind, make, next_serial
from molycow.model.survey import Area, DoseRate, Survey, Wipe
from molycow.store.book import Book
from molycow.store.rows import decimal_in, decimal_out, moment_in, moment_out, text_in


class SurveyRepository:
    """Every round of the building that has been walked."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, survey: Survey) -> Survey:
        with self._book.atomic():
            self._book.execute(
                "INSERT INTO survey (id, ran_at, surveyed_by) VALUES (?, ?, ?)",
                (survey.id, moment_out(survey.at), survey.surveyed_by),
            )
            self._book.execute_many(
                "INSERT INTO survey_reading (survey_id, area, mrem) VALUES (?, ?, ?)",
                [
                    (survey.id, area.value, decimal_out(rate.mrem_per_hour))
                    for area, rate in survey.readings
                ],
            )
            self._book.execute_many(
                """
                INSERT INTO survey_wipe
                  (survey_id, area, spot, counts, background, efficiency)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        survey.id,
                        wipe.area.value,
                        wipe.spot,
                        wipe.counts,
                        wipe.background,
                        decimal_out(wipe.efficiency),
                    )
                    for wipe in survey.wipes
                ],
            )
        return survey

    def find(self, survey_id: str) -> Survey | None:
        row = self._book.one("SELECT * FROM survey WHERE id = ?", (survey_id,))
        if row is None:
            return None
        readings = self._book.all(
            "SELECT * FROM survey_reading WHERE survey_id = ? ORDER BY area", (survey_id,)
        )
        wipes = self._book.all(
            "SELECT * FROM survey_wipe WHERE survey_id = ? ORDER BY spot", (survey_id,)
        )
        return Survey(
            id=text_in(row, "id"),
            at=moment_in(row["ran_at"], "ran_at"),
            surveyed_by=text_in(row, "surveyed_by"),
            readings=tuple(
                (Area(text_in(one, "area")), DoseRate(decimal_in(one["mrem"], "mrem")))
                for one in readings
            ),
            wipes=tuple(
                Wipe(
                    area=Area(text_in(one, "area")),
                    spot=text_in(one, "spot"),
                    counts=int(one["counts"]),
                    background=int(one["background"]),
                    efficiency=decimal_in(one["efficiency"], "efficiency"),
                )
                for one in wipes
            ),
        )

    def get(self, survey_id: str) -> Survey:
        found = self.find(survey_id)
        if found is None:
            raise NotFoundError("no such survey", id=survey_id)
        return found

    def all(self) -> list[Survey]:
        rows = self._book.all("SELECT id FROM survey ORDER BY ran_at, id")
        return [self.get(str(row["id"])) for row in rows]

    def on_day(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Survey]:
        where = tz or zone()
        return [one for one in self.all() if day_of(one.at, where) == day]

    def failures(self, limit: Decimal | None = None) -> list[Survey]:
        found = self.all()
        if limit is None:
            return [one for one in found if not one.passes()]
        return [one for one in found if not one.passes(limit)]

    def next_id(self, day: dt.date) -> str:
        issued = [str(row["id"]) for row in self._book.all("SELECT id FROM survey")]
        return make(Kind.SURVEY, next_serial(issued, Kind.SURVEY, day), day)

    def count(self) -> int:
        return int(self._book.value("SELECT count(*) FROM survey") or 0)
