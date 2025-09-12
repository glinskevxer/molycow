import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import SafetyError, ValidationError
from molycow.model.survey import Area, DoseRate, Wipe
from molycow.service.survey import SurveyService
from molycow.store import Book

DAY = dt.date(2025, 4, 8)
EVENING = at("2025-04-08 17:40")

READINGS = [
    (Area.HOT_LAB, DoseRate.of("1.2")),
    (Area.DISPENSING, DoseRate.of("0.8")),
    (Area.PACKAGING, DoseRate.of("0.3")),
    (Area.WASTE, DoseRate.of("2.1")),
]


def a_wipe(spot: str = "draw station bench top", counts: int = 340) -> Wipe:
    return Wipe(
        area=Area.HOT_LAB,
        spot=spot,
        counts=counts,
        background=120,
        efficiency=Decimal("0.35"),
    )


def test_a_walk_is_numbered_for_the_day(book: Book) -> None:
    service = SurveyService(book)
    survey = service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe()])
    assert survey.id == "SV-250408-01"
    assert survey.passes()


def test_a_walk_with_nothing_on_it_is_refused(book: Book) -> None:
    service = SurveyService(book)
    with pytest.raises(ValidationError, match="no readings"):
        service.walk(EVENING, "K. Ruzicka", [], [])


def test_the_day_needs_every_area_covered(book: Book) -> None:
    service = SurveyService(book)
    with pytest.raises(SafetyError, match="nobody has surveyed"):
        service.require_daily_survey(DAY)
    service.walk(EVENING, "K. Ruzicka", READINGS[:2], [])
    assert service.areas_missed(DAY) == [Area.PACKAGING, Area.WASTE]
    with pytest.raises(SafetyError, match="did not cover every area"):
        service.require_daily_survey(DAY)


def test_a_full_walk_satisfies_the_day(book: Book) -> None:
    service = SurveyService(book)
    walked = service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe()])
    assert service.require_daily_survey(DAY).id == walked.id
    assert service.areas_missed(DAY) == []


def test_a_wipe_covers_its_area_as_well_as_a_reading(book: Book) -> None:
    service = SurveyService(book)
    service.walk(
        EVENING,
        "K. Ruzicka",
        READINGS[:3],
        [Wipe(Area.WASTE, "drum lid", 200, 120, Decimal("0.35"))],
    )
    assert service.areas_missed(DAY) == []


def test_a_dirty_spot_stays_open_until_it_is_wiped_clean(book: Book) -> None:
    service = SurveyService(book)
    service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe(counts=4000)])
    open_ones = service.open_failures()
    assert [one.spot for one in open_ones] == ["draw station bench top"]
    assert not service.is_cleared("draw station bench top")
    assert open_ones[0].note().startswith("draw station bench top at")


def test_a_clean_rewipe_of_the_same_spot_closes_it(book: Book) -> None:
    service = SurveyService(book)
    service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe(counts=4000)])
    service.walk(at("2025-04-08 18:20"), "K. Ruzicka", [], [a_wipe(counts=200)])
    assert service.open_failures() == []
    assert service.is_cleared("draw station bench top")


def test_a_clean_wipe_somewhere_else_does_not_close_it(book: Book) -> None:
    service = SurveyService(book)
    service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe(counts=4000)])
    service.walk(at("2025-04-08 18:20"), "K. Ruzicka", [], [a_wipe(spot="sink", counts=150)])
    assert [one.spot for one in service.open_failures()] == ["draw station bench top"]


def test_an_open_contamination_stops_the_day(book: Book) -> None:
    service = SurveyService(book)
    service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe(counts=4000)])
    with pytest.raises(SafetyError, match="still over the limit"):
        service.require_clean(DAY)
    service.walk(at("2025-04-08 18:20"), "K. Ruzicka", [], [a_wipe(counts=180)])
    service.require_clean(DAY)


def test_a_tighter_limit_reopens_a_spot_that_passed(book: Book) -> None:
    service = SurveyService(book)
    service.walk(EVENING, "K. Ruzicka", READINGS, [a_wipe(counts=600)])
    assert service.open_failures() == []
    assert len(service.open_failures(Decimal(200))) == 1


def test_the_hottest_reading_of_the_day(book: Book) -> None:
    service = SurveyService(book)
    service.walk(EVENING, "K. Ruzicka", READINGS, [])
    worst = service.worst_area_on(DAY)
    assert worst is not None
    assert worst[0] is Area.WASTE
    assert service.worst_area_on(dt.date(2025, 4, 9)) is None
