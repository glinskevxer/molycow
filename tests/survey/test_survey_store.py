import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ConflictError, NotFoundError
from molycow.model.survey import Area, DoseRate, Survey, Wipe
from molycow.store import Book
from molycow.store.surveys import SurveyRepository

WALKED = at("2025-04-08 17:40")


def a_wipe(**changed: object) -> Wipe:
    fields: dict[str, object] = {
        "area": Area.HOT_LAB,
        "spot": "draw station bench top",
        "counts": 340,
        "background": 120,
        "efficiency": Decimal("0.35"),
    }
    fields.update(changed)
    return Wipe(**fields)  # type: ignore[arg-type]


def a_survey(survey_id: str = "SV-250408-02", **changed: object) -> Survey:
    fields: dict[str, object] = {
        "id": survey_id,
        "at": WALKED,
        "surveyed_by": "K. Ruzicka",
        "readings": (
            (Area.HOT_LAB, DoseRate.of("1.2")),
            (Area.RECEPTION, DoseRate.of("0.01")),
        ),
        "wipes": (a_wipe(), a_wipe(spot="fume hood floor", counts=210)),
    }
    fields.update(changed)
    return Survey(**fields)  # type: ignore[arg-type]


def test_a_survey_goes_in_and_comes_back_whole(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    back = repo.get("SV-250408-02")
    assert len(back.readings) == 2
    assert len(back.wipes) == 2
    assert back.surveyed_by == "K. Ruzicka"
    assert back.at == WALKED


def test_the_readings_keep_their_areas_and_their_numbers(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    back = repo.get("SV-250408-02")
    readings = dict(back.readings)
    assert readings[Area.HOT_LAB].mrem_per_hour == Decimal("1.2")
    assert readings[Area.RECEPTION].mrem_per_hour == Decimal("0.01")


def test_the_wipes_keep_the_counts_they_were_taken_with(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    wipes = {one.spot: one for one in repo.get("SV-250408-02").wipes}
    assert wipes["draw station bench top"].counts == 340
    assert wipes["fume hood floor"].dpm == Decimal(257)


def test_the_same_survey_twice_is_a_conflict(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    with pytest.raises(ConflictError):
        repo.add(a_survey())


def test_a_survey_that_is_not_there(book: Book) -> None:
    repo = SurveyRepository(book)
    assert repo.find("SV-250408-09") is None
    with pytest.raises(NotFoundError, match="no such survey"):
        repo.get("SV-250408-09")


def test_surveys_come_back_for_the_day_they_were_walked(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    repo.add(a_survey("SV-250407-01", at=at("2025-04-07 17:20")))
    assert [one.id for one in repo.on_day(dt.date(2025, 4, 8))] == ["SV-250408-02"]
    assert repo.count() == 2


def test_the_failures_are_the_ones_that_did_not_pass(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    repo.add(a_survey("SV-250408-03", wipes=(a_wipe(counts=4000),)))
    assert [one.id for one in repo.failures()] == ["SV-250408-03"]
    assert len(repo.failures(Decimal(200))) == 2


def test_the_next_survey_number_restarts_each_morning(book: Book) -> None:
    repo = SurveyRepository(book)
    assert repo.next_id(dt.date(2025, 4, 8)) == "SV-250408-01"
    repo.add(a_survey())
    assert repo.next_id(dt.date(2025, 4, 8)) == "SV-250408-03"
    assert repo.next_id(dt.date(2025, 4, 9)) == "SV-250409-01"


def test_a_failed_write_leaves_no_half_survey_behind(book: Book) -> None:
    repo = SurveyRepository(book)
    repo.add(a_survey())
    with pytest.raises(ConflictError):
        repo.add(a_survey("SV-250408-02", surveyed_by="P. Vantrease"))
    assert repo.get("SV-250408-02").surveyed_by == "K. Ruzicka"
    assert repo.count() == 1
