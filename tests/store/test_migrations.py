from collections.abc import Iterator

import pytest

from molycow.errors import MolycowError
from molycow.store import Book
from molycow.store.migrations import (
    MIGRATIONS,
    apply,
    is_current,
    latest,
    numbers,
    pending,
    require_current,
    schema_version,
)


@pytest.fixture
def book() -> Iterator[Book]:
    with Book.in_memory() as opened:
        yield opened


def test_a_fresh_book_is_at_version_zero(book: Book) -> None:
    assert schema_version(book) == 0
    assert not is_current(book)
    assert len(pending(book)) == len(MIGRATIONS)


def test_applying_brings_the_book_up_to_the_latest(book: Book) -> None:
    ran = apply(book)
    assert [step.number for step in ran] == list(numbers())
    assert schema_version(book) == latest()
    assert is_current(book)
    assert pending(book) == ()


def test_applying_twice_does_nothing_the_second_time(book: Book) -> None:
    apply(book)
    assert apply(book) == ()


def test_the_steps_are_numbered_from_one_with_no_gaps() -> None:
    assert list(numbers()) == list(range(1, len(MIGRATIONS) + 1))


def test_every_step_has_a_name_and_some_sql() -> None:
    for step in MIGRATIONS:
        assert step.name.strip()
        assert "CREATE" in step.statements or "ALTER" in step.statements


def test_a_book_can_be_stopped_part_way(book: Book) -> None:
    apply(book, upto=1)
    assert schema_version(book) == 1


def test_a_step_that_does_not_exist_is_refused(book: Book) -> None:
    with pytest.raises(MolycowError, match="there is no migration"):
        apply(book, upto=latest() + 5)


def test_the_core_register_tables_are_there_after_the_first_step(book: Book) -> None:
    apply(book, upto=1)
    names = {row["name"] for row in book.all("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"customer", "authorized_user", "authorized_nuclide"} <= names


def test_a_book_behind_the_code_is_refused_work(book: Book) -> None:
    with pytest.raises(MolycowError, match="not at the schema"):
        require_current(book)
    apply(book)
    require_current(book)


def test_a_customer_has_to_be_one_of_the_kinds_we_know(book: Book) -> None:
    apply(book)
    with pytest.raises(MolycowError):
        book.execute(
            "INSERT INTO customer VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "CU-0001",
                "Saint Brannon",
                "shop",
                "L-1",
                "1 Way",
                "Ardmore",
                "north",
                "2025-01-06",
                None,
            ),
        )
