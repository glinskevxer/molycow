import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_kit_lot, an_elution

from molycow.errors import NotFoundError, RuleError, ValidationError
from molycow.model.fridge import HIGHEST, LOWEST, FridgeReading
from molycow.service.compound import CompoundService
from molycow.service.fridge import FridgeService
from molycow.store import Book
from molycow.store.fridge import FridgeRepository
from molycow.units import Activity

MORNING = at("2025-04-08 06:10")


def a_reading(**changed: object) -> FridgeReading:
    fields: dict[str, object] = {
        "read_at": MORNING,
        "celsius": Decimal("4.5"),
        "read_by": "K. Ruzicka",
    }
    fields.update(changed)
    return FridgeReading(**fields)  # type: ignore[arg-type]


def test_the_range_is_two_to_eight() -> None:
    assert Decimal(2) == LOWEST
    assert Decimal(8) == HIGHEST
    assert a_reading().in_range
    assert a_reading(celsius=Decimal(2)).in_range
    assert a_reading(celsius=Decimal(8)).in_range
    assert a_reading(celsius=Decimal("11.5")).is_excursion


def test_a_reading_in_range_prints_plainly() -> None:
    assert a_reading().line().endswith("in range")


def test_an_excursion_stays_open_until_it_is_reviewed() -> None:
    warm = a_reading(celsius=Decimal("11.5"))
    assert warm.is_open
    assert "EXCURSION" in warm.line()
    looked = warm.reviewed(at("2025-04-08 08:00"), "P. Vantrease")
    assert not looked.is_open
    assert "reviewed by P. Vantrease" in looked.line()


def test_a_reading_in_range_does_not_need_reviewing() -> None:
    with pytest.raises(ValidationError, match="does not need reviewing"):
        a_reading().reviewed(at("2025-04-08 08:00"), "P. Vantrease")


def test_an_excursion_is_reviewed_once() -> None:
    warm = a_reading(celsius=Decimal("11.5")).reviewed(at("2025-04-08 08:00"), "P. V")
    with pytest.raises(ValidationError, match="already been reviewed"):
        warm.reviewed(at("2025-04-08 09:00"), "P. V")


def test_a_reading_says_who_took_it_and_reads_like_a_thermometer() -> None:
    with pytest.raises(ValidationError, match="says who took it"):
        a_reading(read_by=" ")
    with pytest.raises(ValidationError, match="not a reading off a fridge"):
        a_reading(celsius=Decimal(200))


def test_a_review_has_both_halves_or_neither() -> None:
    with pytest.raises(ValidationError, match="both a moment and a name"):
        a_reading(celsius=Decimal(11), reviewed_at=at("2025-04-08 08:00"))
    with pytest.raises(ValidationError, match="reviewed before it was taken"):
        a_reading(
            celsius=Decimal(11),
            reviewed_at=at("2025-04-08 05:00"),
            reviewed_by="P. V",
        )


def test_the_log_reads_back_by_day(book: Book) -> None:
    service = FridgeService(book)
    service.record(MORNING, Decimal("4.5"), "K. Ruzicka")
    service.record(at("2025-04-09 06:10"), Decimal("5.0"), "K. Ruzicka")
    assert len(service.readings_on(dt.date(2025, 4, 8))) == 1
    latest = service.latest()
    assert latest is not None
    assert latest.celsius == Decimal("5.0")


def test_an_open_excursion_is_found_and_then_closed(book: Book) -> None:
    service = FridgeService(book)
    service.record(MORNING, Decimal("11.5"), "K. Ruzicka")
    assert not service.is_clear()
    assert len(service.open_excursions()) == 1
    service.review(MORNING, at("2025-04-08 08:00"), "P. Vantrease")
    assert service.is_clear()
    assert len(FridgeRepository(book).excursions()) == 1


def test_a_review_of_a_reading_nobody_took(book: Book) -> None:
    service = FridgeService(book)
    with pytest.raises(NotFoundError, match="no reading was taken"):
        service.review(MORNING, at("2025-04-08 08:00"), "P. Vantrease")


def test_an_open_excursion_stops_a_refrigerated_kit(book: Book) -> None:
    elution_id = an_elution(book)
    a_kit_lot(book, "KL-0114", code="MAA")
    FridgeService(book).record(MORNING, Decimal("11.5"), "K. Ruzicka")
    service = CompoundService(book)
    with pytest.raises(RuleError, match="excursion nobody has reviewed"):
        service.compound("MAA", elution_id, at("2025-04-08 07:15"), Activity.of(100, "mci"), "K")


def test_a_kit_that_lives_on_the_shelf_is_not_stopped(book: Book) -> None:
    elution_id = an_elution(book)
    a_kit_lot(book)
    FridgeService(book).record(MORNING, Decimal("11.5"), "K. Ruzicka")
    batch = CompoundService(book).compound(
        "MDP", elution_id, at("2025-04-08 07:15"), Activity.of(300, "mci"), "K. Ruzicka"
    )
    assert batch.id == "B-250408-01"


def test_a_reviewed_excursion_lets_the_kit_through(book: Book) -> None:
    elution_id = an_elution(book)
    a_kit_lot(book, "KL-0114", code="MAA")
    fridge = FridgeService(book)
    fridge.record(MORNING, Decimal("11.5"), "K. Ruzicka")
    fridge.review(MORNING, at("2025-04-08 06:40"), "P. Vantrease")
    batch = CompoundService(book).compound(
        "MAA", elution_id, at("2025-04-08 07:15"), Activity.of(100, "mci"), "K. Ruzicka"
    )
    assert batch.code == "MAA"
