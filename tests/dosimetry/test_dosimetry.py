import datetime as dt
from decimal import Decimal

import pytest

from molycow.errors import ConflictError, NotFoundError, ValidationError
from molycow.model.badge import DEEP_LIMIT_MREM, Badge, quarter_of
from molycow.service.dosimetry import DosimetryService
from molycow.store import Book
from molycow.store.badges import BadgeRepository

READ_ON = dt.date(2025, 7, 14)


def a_badge(**changed: object) -> Badge:
    fields: dict[str, object] = {
        "person": "K. Ruzicka",
        "period": "2025Q2",
        "deep_mrem": Decimal(120),
        "extremity_mrem": Decimal(1400),
        "read_on": READ_ON,
    }
    fields.update(changed)
    return Badge(**fields)  # type: ignore[arg-type]


def test_a_badge_period_reads_like_a_quarter() -> None:
    assert a_badge().year == 2025
    assert a_badge().quarter == 2
    assert quarter_of(dt.date(2025, 4, 8)) == "2025Q2"
    assert quarter_of(dt.date(2025, 12, 31)) == "2025Q4"


def test_a_badge_that_is_not_a_badge_is_refused() -> None:
    with pytest.raises(ValidationError, match="belongs to somebody"):
        a_badge(person=" ")
    with pytest.raises(ValidationError, match="reads like '2025Q2'"):
        a_badge(period="second quarter")
    with pytest.raises(ValidationError, match="below zero"):
        a_badge(deep_mrem=Decimal(-1))


def test_a_quiet_quarter_is_not_investigated() -> None:
    assert not a_badge().over_investigation_level
    assert a_badge().line().endswith("mrem")


def test_a_quarter_over_a_tenth_of_the_year_is_investigated() -> None:
    busy = a_badge(deep_mrem=DEEP_LIMIT_MREM / Decimal(10) + Decimal(1))
    assert busy.over_investigation_level
    assert "investigate" in busy.line()


def test_a_reading_goes_in_and_comes_back(book: Book) -> None:
    repo = BadgeRepository(book)
    repo.add(a_badge())
    assert repo.get("K. Ruzicka", "2025Q2") == a_badge()
    assert repo.people() == ["K. Ruzicka"]


def test_a_badge_that_has_not_come_back(book: Book) -> None:
    repo = BadgeRepository(book)
    assert repo.find("K. Ruzicka", "2025Q2") is None
    with pytest.raises(NotFoundError, match="no badge reading"):
        repo.get("K. Ruzicka", "2025Q2")


def test_a_quarter_is_read_once(book: Book) -> None:
    service = DosimetryService(book)
    service.record("K. Ruzicka", "2025Q2", Decimal(120), Decimal(1400), READ_ON)
    with pytest.raises(ConflictError, match="already been read"):
        service.record("K. Ruzicka", "2025Q2", Decimal(130), Decimal(1500), READ_ON)


def test_the_year_adds_the_quarters_up(book: Book) -> None:
    service = DosimetryService(book)
    service.record("K. Ruzicka", "2025Q1", Decimal(200), Decimal(2100), READ_ON)
    service.record("K. Ruzicka", "2025Q2", Decimal(180), Decimal(1900), READ_ON)
    so_far = service.year_to_date("K. Ruzicka", 2025)
    assert so_far.deep == Decimal(380)
    assert so_far.extremity == Decimal(4000)
    assert so_far.share_used() == Decimal("7.6")
    assert not so_far.over_limit


def test_a_year_over_the_limit_says_so(book: Book) -> None:
    service = DosimetryService(book)
    service.record("K. Ruzicka", "2025Q1", Decimal(3000), Decimal(2100), READ_ON)
    service.record("K. Ruzicka", "2025Q2", Decimal(2500), Decimal(1900), READ_ON)
    so_far = service.year_to_date("K. Ruzicka", 2025)
    assert so_far.over_limit
    assert "OVER THE LIMIT" in so_far.line()


def test_the_watch_list_is_worst_first(book: Book) -> None:
    service = DosimetryService(book)
    service.record("K. Ruzicka", "2025Q1", Decimal(600), Decimal(2100), READ_ON)
    service.record("P. Vantrease", "2025Q1", Decimal(5200), Decimal(1900), READ_ON)
    service.record("J. Fennimore", "2025Q1", Decimal(90), Decimal(900), READ_ON)
    watched = service.watch_list(2025)
    assert [one.year_to_date.person for one in watched] == ["P. Vantrease", "K. Ruzicka"]
    assert watched[0].reason == "over the yearly limit"
    assert watched[1].reason == "a quarter over the investigation level"
    assert "over the yearly limit" in watched[0].line()


def test_a_badge_nobody_sent_back_is_missing(book: Book) -> None:
    service = DosimetryService(book)
    service.record("K. Ruzicka", "2025Q1", Decimal(120), Decimal(1400), READ_ON)
    service.record("P. Vantrease", "2025Q1", Decimal(90), Decimal(900), READ_ON)
    service.record("K. Ruzicka", "2025Q2", Decimal(120), Decimal(1400), READ_ON)
    assert service.missing("2025Q2") == ["P. Vantrease"]
    assert service.missing("2025Q1") == []


def test_the_quarter_of_a_day_is_the_period_it_belongs_to(book: Book) -> None:
    assert DosimetryService(book).period_for(dt.date(2025, 8, 4)) == "2025Q3"


def test_an_empty_year_is_not_on_the_watch_list(book: Book) -> None:
    service = DosimetryService(book)
    service.record("K. Ruzicka", "2025Q1", Decimal(600), Decimal(2100), READ_ON)
    assert service.watch_list(2024) == []
