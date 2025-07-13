from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import CLEAN_SALINE, CLEAN_SOLVENT, a_batch

from molycow.errors import NotFoundError, ReleaseError
from molycow.model.purity import Strip, System
from molycow.service.purity import PurityService
from molycow.store import Book
from molycow.store.kits import BatchRepository

PREP = at("2025-04-08 07:15")
TESTED = at("2025-04-08 07:35")


def test_a_clean_reading_releases_the_batch(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    reading = service.run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    assert reading.released
    assert reading.rcp == Decimal("95.9")
    assert reading.note() == "95.9% against a floor of 90%"
    assert service.released(batch_id)


def test_the_purity_is_written_onto_the_batch_as_well(book: Book) -> None:
    batch_id = a_batch(book)
    PurityService(book).run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    assert BatchRepository(book).get(batch_id).rcp == Decimal("95.9")


def test_a_dirty_reading_holds_the_batch_and_names_the_impurity(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    reading = service.run(
        batch_id,
        TESTED,
        Strip(System.SOLVENT, origin=40000, front=9000),
        CLEAN_SALINE,
        "K. Ruzicka",
    )
    assert not reading.released
    assert reading.note() == "held at 79.7%, mostly free pertechnetate"
    assert not service.released(batch_id)
    assert [one.id for one in service.failures()] == [batch_id]


def test_a_held_batch_cannot_be_drawn_from(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    with pytest.raises(ReleaseError, match="no purity reading yet"):
        service.require_released(batch_id, at("2025-04-08 08:00"))
    service.run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    assert service.require_released(batch_id, at("2025-04-08 08:00")).id == batch_id


def test_a_released_batch_still_runs_out_of_time(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    service.run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    with pytest.raises(ReleaseError, match="past its expiry"):
        service.require_released(batch_id, at("2025-04-08 14:00"))


def test_a_batch_cannot_be_tested_before_it_was_made(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    with pytest.raises(ReleaseError, match="before it was made"):
        service.run(batch_id, at("2025-04-08 07:00"), CLEAN_SOLVENT, CLEAN_SALINE, "K. R")


def test_the_counts_are_kept_and_not_just_the_percentage(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    service.run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    kept = service.reading_for(batch_id)
    assert kept.solvent.origin == 48200
    assert kept.saline.front == 47600
    assert kept.tested_by == "K. Ruzicka"
    assert kept.tested_at == TESTED


def test_a_batch_with_no_reading(book: Book) -> None:
    service = PurityService(book)
    with pytest.raises(NotFoundError, match="no such batch"):
        service.released("B-250408-09")
    batch_id = a_batch(book)
    with pytest.raises(NotFoundError, match="no purity reading"):
        service.reading_for(batch_id)


def test_a_batch_is_tested_once(book: Book) -> None:
    batch_id = a_batch(book)
    service = PurityService(book)
    service.run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    with pytest.raises(Exception, match="already in the book"):
        service.run(batch_id, TESTED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    assert BatchRepository(book).get(batch_id).rcp == Decimal("95.9")
