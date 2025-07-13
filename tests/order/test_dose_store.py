import datetime as dt

import pytest
from tests.conftest import at
from tests.support import a_batch, a_register, an_order

from molycow.errors import ConflictError, NotFoundError
from molycow.model.dose import Dose
from molycow.store import Book
from molycow.store.doses import DoseRepository
from molycow.units import Activity, Volume

DRAWN = at("2025-04-08 07:40")
CALIBRATION = at("2025-04-08 09:00")


def a_day(book: Book) -> str:
    """A register, an open order and a batch to fill it from."""
    a_register(book)
    an_order(book)
    return a_batch(book)


def a_dose(dose_id: str = "DS-250408-14", **changed: object) -> Dose:
    fields: dict[str, object] = {
        "id": dose_id,
        "order_id": "ORD-250407-11",
        "batch_id": "B-250408-01",
        "code": "MDP",
        "drawn_at": DRAWN,
        "calibration_at": CALIBRATION,
        "volume": Volume.of("0.55"),
        "assayed": Activity.of("24.6", "mci"),
        "drawn_by": "K. Ruzicka",
    }
    fields.update(changed)
    return Dose(**fields)  # type: ignore[arg-type]


def test_a_dose_goes_in_and_comes_back_the_same(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    assert repo.get("DS-250408-14") == a_dose()


def test_a_dose_needs_an_order_and_a_batch_that_exist(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        DoseRepository(book).add(a_dose())


def test_an_order_is_only_filled_once(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    with pytest.raises(ConflictError):
        repo.add(a_dose("DS-250408-15"))


def test_a_dose_is_found_by_its_order_and_its_batch(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    found = repo.for_order("ORD-250407-11")
    assert found is not None
    assert found.id == "DS-250408-14"
    assert [one.id for one in repo.for_batch("B-250408-01")] == ["DS-250408-14"]
    assert repo.for_order("ORD-250407-12") is None


def test_the_days_doses_are_the_ones_drawn_that_day(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    assert repo.count_on(dt.date(2025, 4, 8)) == 1
    assert repo.on_day(dt.date(2025, 4, 9)) == []


def test_the_next_dose_number_restarts_each_morning(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    assert repo.next_id(dt.date(2025, 4, 8)) == "DS-250408-01"
    repo.add(a_dose())
    assert repo.next_id(dt.date(2025, 4, 8)) == "DS-250408-15"
    assert repo.next_id(dt.date(2025, 4, 9)) == "DS-250409-01"


def test_a_dose_that_is_not_there(book: Book) -> None:
    repo = DoseRepository(book)
    assert repo.find("DS-250408-99") is None
    with pytest.raises(NotFoundError, match="no such dose"):
        repo.get("DS-250408-99")
