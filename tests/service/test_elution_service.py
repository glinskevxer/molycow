import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import RuleError
from molycow.model.generator import Generator
from molycow.service.elution import ElutionService
from molycow.store import Book
from molycow.store.generators import GeneratorRepository
from molycow.units import Activity, Volume


def a_generator(book: Book, generator_id: str = "GEN-0027", **changed: object) -> Generator:
    fields: dict[str, object] = {
        "id": generator_id,
        "serial": f"M99-{generator_id[-4:]}",
        "maker": "Corren Isotopes",
        "calibrated_at": at("2025-04-05 12:00"),
        "calibrated_activity": Activity.of(2, "Ci"),
        "received_on": dt.date(2025, 4, 5),
        "expires_on": dt.date(2025, 4, 19),
    }
    fields.update(changed)
    return GeneratorRepository(book).add(Generator(**fields))  # type: ignore[arg-type]


def test_the_first_milking_is_worked_from_the_makers_calibration(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    expected = service.expected_from("GEN-0027", at("2025-04-08 06:30"))
    assert expected.format("mci", 0) == "960 mCi"


def test_a_milking_is_numbered_for_the_day_it_happened(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    first = service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(900, "mCi"))
    assert first.elution.id == "EL-250408-01"
    second = service.milk(
        "GEN-0027", at("2025-04-08 13:00"), Volume.of(10), Activity.of(430, "mCi")
    )
    assert second.elution.id == "EL-250408-02"


def test_the_second_milking_of_the_day_expects_much_less(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    first = service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(900, "mCi"))
    second = service.milk(
        "GEN-0027", at("2025-04-08 13:00"), Volume.of(10), Activity.of(430, "mCi")
    )
    assert second.elution.expected < first.elution.expected


def test_a_good_yield_carries_no_note(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    milking = service.milk(
        "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(940, "mCi")
    )
    assert milking.note is None
    assert milking.percent > Decimal(90)


def test_a_low_yield_is_recorded_with_a_note(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    milking = service.milk(
        "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(790, "mCi")
    )
    assert milking.note == "low yield, watch the column"


def test_a_poor_yield_stops_the_elution_until_somebody_overrides_it(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    with pytest.raises(RuleError, match="far less than it should"):
        service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(400, "mCi"))
    forced = service.milk(
        "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(400, "mCi"), force=True
    )
    assert forced.note == "poor yield, accepted by override"


def test_a_refused_elution_leaves_nothing_in_the_book(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    with pytest.raises(RuleError):
        service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(400, "mCi"))
    assert book.value("SELECT count(*) FROM elution") == 0


def test_more_than_expected_is_a_calibration_question(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    milking = service.milk(
        "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of("1.2", "Ci")
    )
    assert milking.note == "more came off than was expected, check the calibration"


def test_an_expired_column_cannot_be_milked(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    with pytest.raises(RuleError, match="cannot be milked on that day"):
        service.milk("GEN-0027", at("2025-04-20 06:30"), Volume.of(10), Activity.of(90, "mCi"))


def test_a_column_cannot_be_milked_backwards(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    service.milk("GEN-0027", at("2025-04-08 13:00"), Volume.of(10), Activity.of(900, "mCi"))
    with pytest.raises(RuleError, match="already milked"):
        service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(900, "mCi"))


def test_what_is_left_in_a_vial_falls_and_then_stops_counting(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    milking = service.milk(
        "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(940, "mCi")
    )
    at_noon = service.available_at(milking.elution.id, at("2025-04-08 12:30"))
    assert at_noon.format("mci", 0) == "470 mCi"
    assert service.available_at(milking.elution.id, at("2025-04-08 19:00")).is_zero()


def test_the_strongest_vial_on_the_bench_is_the_one_to_draw_from(book: Book) -> None:
    a_generator(book)
    a_generator(book, "GEN-0028")
    service = ElutionService(book)
    service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(900, "mCi"))
    service.milk("GEN-0028", at("2025-04-08 07:00"), Volume.of(5), Activity.of(700, "mCi"))
    strongest = service.strongest_at(at("2025-04-08 08:00"))
    assert strongest is not None
    assert strongest.generator_id == "GEN-0028"
    assert len(service.in_date_eluates(at("2025-04-08 08:00"))) == 2


def test_nothing_is_on_the_bench_the_next_morning(book: Book) -> None:
    a_generator(book)
    service = ElutionService(book)
    service.milk("GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(900, "mCi"))
    assert service.in_date_eluates(at("2025-04-09 06:30")) == []
    assert service.strongest_at(at("2025-04-09 06:30")) is None


def test_the_service_knows_which_daughter_it_is_handling(book: Book) -> None:
    assert ElutionService(book).daughter_symbol() == "Tc-99m"
