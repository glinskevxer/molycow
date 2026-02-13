import pytest
from tests.conftest import at
from tests.support import a_batch

from molycow.errors import ConflictError, NotFoundError
from molycow.model.purity import PurityTest, Strip, System
from molycow.store import Book
from molycow.store.purity import PurityRepository

TESTED = at("2025-04-08 07:35")


def a_reading(batch_id: str, **changed: object) -> PurityTest:
    fields: dict[str, object] = {
        "batch_id": batch_id,
        "tested_at": TESTED,
        "solvent": Strip(System.SOLVENT, origin=48200, front=1100, background=40),
        "saline": Strip(System.SALINE, origin=900, front=47600, background=40),
        "tested_by": "K. Ruzicka",
    }
    fields.update(changed)
    return PurityTest(**fields)  # type: ignore[arg-type]


def test_a_reading_goes_in_and_comes_back_with_its_counts(book: Book) -> None:
    batch_id = a_batch(book)
    repo = PurityRepository(book)
    repo.add(a_reading(batch_id))
    back = repo.get(batch_id)
    assert back.solvent.origin == 48200
    assert back.solvent.background == 40
    assert back.saline.front == 47600
    assert back.rcp == a_reading(batch_id).rcp


def test_a_batch_is_read_once(book: Book) -> None:
    batch_id = a_batch(book)
    repo = PurityRepository(book)
    repo.add(a_reading(batch_id))
    with pytest.raises(ConflictError):
        repo.add(a_reading(batch_id))


def test_a_reading_needs_a_batch_that_exists(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        PurityRepository(book).add(a_reading("B-250408-09"))


def test_a_batch_with_no_reading(book: Book) -> None:
    repo = PurityRepository(book)
    assert repo.find("B-250408-09") is None
    with pytest.raises(NotFoundError, match="no purity reading"):
        repo.get("B-250408-09")


def test_the_readings_come_back_in_the_order_they_were_run(book: Book) -> None:
    batch_id = a_batch(book)
    repo = PurityRepository(book)
    repo.add(a_reading(batch_id))
    assert [one.batch_id for one in repo.all()] == [batch_id]
