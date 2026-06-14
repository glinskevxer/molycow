import datetime as dt

import pytest
from tests.support import a_generator, a_kit_lot, an_elution

from molycow.ids import Kind
from molycow.store import Book
from molycow.store.serials import TABLES, issued, next_id

DAY = dt.date(2025, 4, 8)


def test_a_fresh_book_starts_every_kind_at_one(book: Book) -> None:
    assert next_id(book, Kind.GENERATOR) == "GEN-0001"
    assert next_id(book, Kind.KIT_LOT) == "KL-0001"
    assert next_id(book, Kind.ELUTION, DAY) == "EL-250408-01"


def test_the_next_number_follows_what_is_in_the_book(book: Book) -> None:
    a_generator(book)
    assert next_id(book, Kind.GENERATOR) == "GEN-0028"
    a_kit_lot(book)
    assert next_id(book, Kind.KIT_LOT) == "KL-0115"


def test_a_daily_number_restarts_each_morning(book: Book) -> None:
    an_elution(book)
    assert next_id(book, Kind.ELUTION, DAY) == "EL-250408-02"
    assert next_id(book, Kind.ELUTION, dt.date(2025, 4, 9)) == "EL-250409-01"


def test_the_numbers_already_handed_out_come_off_the_table(book: Book) -> None:
    a_generator(book)
    assert issued(book, Kind.GENERATOR) == ["GEN-0027"]
    assert issued(book, Kind.DOSE) == []


def test_every_kind_that_is_numbered_has_a_table() -> None:
    for kind in Kind:
        assert kind in TABLES


def test_a_kind_nobody_numbered_is_a_programming_error(book: Book) -> None:
    del TABLES[Kind.ROUTE]
    try:
        with pytest.raises(KeyError):
            issued(book, Kind.ROUTE)
    finally:
        TABLES[Kind.ROUTE] = "route"
