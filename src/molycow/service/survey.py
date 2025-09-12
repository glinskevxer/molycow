"""Walking the building, and what a bad reading obliges the pharmacy to do.

A failed survey is not closed by writing it down. The spot is cleaned and
wiped again, and until a later survey covers that same spot and comes back
clean, the failure is still open. That is the rule this service exists to
enforce, because it is the one a busy afternoon quietly skips.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import SafetyError, ValidationError
from molycow.model.survey import WIPE_LIMIT_DPM, Area, DoseRate, Survey, Wipe
from molycow.store.book import Book
from molycow.store.surveys import SurveyRepository

DAILY_AREAS = (Area.HOT_LAB, Area.DISPENSING, Area.PACKAGING, Area.WASTE)


@dataclass(frozen=True)
class OpenFailure:
    """A spot that failed and has not come back clean since."""

    survey_id: str
    spot: str
    dpm: Decimal
    found_at: dt.datetime

    def note(self) -> str:
        return f"{self.spot} at {self.dpm} dpm, found on {self.survey_id}"


class SurveyService:
    """The survey round."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._surveys = SurveyRepository(book)

    def walk(
        self,
        at: dt.datetime,
        surveyed_by: str,
        readings: list[tuple[Area, DoseRate]],
        wipes: list[Wipe],
    ) -> Survey:
        """Write down a round of the building."""
        if not readings and not wipes:
            raise ValidationError("a survey with no readings is not a survey")
        survey = Survey(
            id=self._surveys.next_id(day_of(at, self._tz)),
            at=at,
            surveyed_by=surveyed_by,
            readings=tuple(readings),
            wipes=tuple(wipes),
        )
        self._surveys.add(survey)
        return survey

    def areas_missed(self, day: dt.date) -> list[Area]:
        """The areas that should have been surveyed today and were not."""
        walked: set[Area] = set()
        for survey in self._surveys.on_day(day, self._tz):
            walked.update(area for area, _ in survey.readings)
            walked.update(wipe.area for wipe in survey.wipes)
        return [area for area in DAILY_AREAS if area not in walked]

    def open_failures(self, limit: Decimal = WIPE_LIMIT_DPM) -> list[OpenFailure]:
        """Dirty spots with no clean wipe of the same spot after them."""
        surveys = self._surveys.all()
        open_ones: dict[str, OpenFailure] = {}
        for survey in surveys:
            for wipe in survey.wipes:
                if wipe.is_clean(limit):
                    open_ones.pop(wipe.spot, None)
                else:
                    open_ones[wipe.spot] = OpenFailure(survey.id, wipe.spot, wipe.dpm, survey.at)
        return sorted(open_ones.values(), key=lambda one: one.found_at)

    def is_cleared(self, spot: str, limit: Decimal = WIPE_LIMIT_DPM) -> bool:
        return all(one.spot != spot for one in self.open_failures(limit))

    def require_clean(self, day: dt.date, limit: Decimal = WIPE_LIMIT_DPM) -> None:
        """Refuse to carry on with a contamination still open."""
        open_ones = self.open_failures(limit)
        if open_ones:
            raise SafetyError(
                "contamination-open",
                f"a spot is still over the limit: {open_ones[0].note()}",
                day=day.isoformat(),
            )

    def require_daily_survey(self, day: dt.date) -> Survey:
        """The day's survey, or a stop because nobody walked the building."""
        walked = self._surveys.on_day(day, self._tz)
        if not walked:
            raise SafetyError(
                "survey-missing", "nobody has surveyed the building today", day=day.isoformat()
            )
        missed = self.areas_missed(day)
        if missed:
            raise SafetyError(
                "survey-partial",
                "the day's survey did not cover every area",
                missed=", ".join(area.value for area in missed),
            )
        return walked[-1]

    def worst_area_on(self, day: dt.date) -> tuple[Area, DoseRate] | None:
        """The hottest reading of the day, for the top of the sheet."""
        readings: list[tuple[Area, DoseRate]] = []
        for survey in self._surveys.on_day(day, self._tz):
            readings.extend(survey.readings)
        if not readings:
            return None
        return max(readings, key=lambda pair: pair[1].mrem_per_hour)
