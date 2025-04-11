import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import NotFoundError, ReleaseError
from molycow.model.generator import Generator
from molycow.service.breakthrough import BreakthroughService
from molycow.service.elution import ElutionService
from molycow.store import Book
from molycow.store.breakthrough import BreakthroughRepository
from molycow.store.generators import GeneratorRepository
from molycow.units import Activity, Volume

DRAWN = at("2025-04-08 06:30")
TESTED = at("2025-04-08 06:45")


def a_bench(book: Book) -> str:
    GeneratorRepository(book).add(
        Generator(
            id="GEN-0027",
            serial="M99-44182",
            maker="Corren Isotopes",
            calibrated_at=at("2025-04-05 12:00"),
            calibrated_activity=Activity.of(2, "Ci"),
            received_on=dt.date(2025, 4, 5),
            expires_on=dt.date(2025, 4, 19),
        )
    )
    milking = ElutionService(book).milk("GEN-0027", DRAWN, Volume.of(10), Activity.of(940, "mCi"))
    return milking.elution.id


def test_a_test_measures_against_the_technetium_in_the_vial_now(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    reading = service.test(elution_id, TESTED, Activity.of("0.9", "uci"), Decimal(4), "K. Ruzicka")
    assert reading.technetium.format("mci", 0) == "913 mCi"
    assert reading.passes


def test_a_test_cannot_be_run_before_the_elution(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    with pytest.raises(ReleaseError, match="before it was drawn"):
        service.test(
            elution_id, at("2025-04-08 06:00"), Activity.of("0.9", "uci"), Decimal(4), "K. R"
        )


def test_an_untested_eluate_cannot_be_used(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    with pytest.raises(ReleaseError, match="has not been tested"):
        service.release(elution_id)
    assert not service.may_draw(elution_id, at("2025-04-08 08:00"))
    assert service.untested() == [elution_id]


def test_a_clean_vial_is_good_for_its_shelf_life(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    service.test(elution_id, TESTED, Activity.of("0.9", "uci"), Decimal(4), "K. Ruzicka")
    release = service.release(elution_id)
    assert release.good_until == at("2025-04-08 18:30")
    assert release.ends_because == "twelve hour shelf life"
    assert service.untested() == []


def test_a_dirty_vial_ends_before_its_shelf_life(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    service.test(elution_id, TESTED, Activity.of(80, "uci"), Decimal(4), "K. Ruzicka")
    release = service.release(elution_id)
    assert release.good_until < at("2025-04-08 18:30")
    assert release.ends_because == "molybdenum ratio reaches the limit"
    assert service.may_draw(elution_id, at("2025-04-08 08:00"))
    assert not service.may_draw(elution_id, at("2025-04-08 17:00"))


def test_a_vial_over_the_moly_limit_is_refused_outright(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    service.test(elution_id, TESTED, Activity.of(400, "uci"), Decimal(4), "K. Ruzicka")
    with pytest.raises(ReleaseError, match="molybdenum breakthrough"):
        service.release(elution_id)


def test_a_vial_over_the_aluminium_limit_is_refused_outright(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    service.test(elution_id, TESTED, Activity.of("0.9", "uci"), Decimal(14), "K. Ruzicka")
    with pytest.raises(ReleaseError, match="aluminium over the limit"):
        service.release(elution_id)
    assert BreakthroughRepository(book).failures()[0].elution_id == elution_id


def test_a_vial_cannot_be_drawn_from_before_it_was_drawn(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    service.test(elution_id, TESTED, Activity.of("0.9", "uci"), Decimal(4), "K. Ruzicka")
    assert not service.may_draw(elution_id, at("2025-04-08 06:00"))


def test_a_test_against_an_elution_that_is_not_there(book: Book) -> None:
    service = BreakthroughService(book)
    with pytest.raises(NotFoundError, match="no such elution"):
        service.test("EL-250408-09", TESTED, Activity.of(1, "uci"), Decimal(4), "K. R")
    with pytest.raises(NotFoundError, match="has not been tested"):
        BreakthroughRepository(book).get("EL-250408-09")


def test_a_vial_is_tested_once(book: Book) -> None:
    elution_id = a_bench(book)
    service = BreakthroughService(book)
    service.test(elution_id, TESTED, Activity.of("0.9", "uci"), Decimal(4), "K. Ruzicka")
    with pytest.raises(Exception, match="already in the book"):
        service.test(elution_id, TESTED, Activity.of("0.9", "uci"), Decimal(4), "K. Ruzicka")
