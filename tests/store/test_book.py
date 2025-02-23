from collections.abc import Iterator
from pathlib import Path

import pytest

from molycow.errors import ConflictError, MolycowError, ValidationError
from molycow.store import Book
from molycow.store.book import split_statements

SETUP = """
CREATE TABLE parent (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE child (
  id TEXT PRIMARY KEY,
  parent_id TEXT NOT NULL REFERENCES parent(id)
);
"""


@pytest.fixture
def book() -> Iterator[Book]:
    with Book.in_memory() as opened:
        opened.script(SETUP)
        yield opened


def test_a_memory_book_has_no_path(book: Book) -> None:
    assert book.path is None
    assert not book.closed


def test_a_book_on_disk_remembers_where_it_is(tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    with Book.open(target) as opened:
        opened.script(SETUP)
        opened.execute("INSERT INTO parent VALUES (?, ?)", ("CU-0001", "Saint Brannon"))
    assert target.exists()
    with Book.open(target) as reopened:
        assert reopened.value("SELECT name FROM parent") == "Saint Brannon"


def test_opening_a_book_in_a_folder_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="no folder"):
        Book.open(tmp_path / "nowhere" / "day.sqlite3")


def test_rows_come_back_by_column_name(book: Book) -> None:
    book.execute("INSERT INTO parent VALUES (?, ?)", ("CU-0001", "Saint Brannon"))
    row = book.one("SELECT * FROM parent")
    assert row is not None
    assert row["name"] == "Saint Brannon"


def test_a_missing_row_is_none_not_an_error(book: Book) -> None:
    assert book.one("SELECT * FROM parent WHERE id = ?", ("CU-0404",)) is None
    assert book.value("SELECT name FROM parent WHERE id = ?", ("CU-0404",)) is None
    assert book.all("SELECT * FROM parent") == []


def test_a_duplicate_key_reads_as_a_conflict(book: Book) -> None:
    book.execute("INSERT INTO parent VALUES (?, ?)", ("CU-0001", "Saint Brannon"))
    with pytest.raises(ConflictError, match="already in the book"):
        book.execute("INSERT INTO parent VALUES (?, ?)", ("CU-0001", "Saint Brannon"))


def test_foreign_keys_are_on(book: Book) -> None:
    with pytest.raises(ValidationError, match="not there"):
        book.execute("INSERT INTO child VALUES (?, ?)", ("X-1", "CU-0404"))


def test_a_statement_that_makes_no_sense_reads_as_our_error(book: Book) -> None:
    with pytest.raises(MolycowError, match="would not take that"):
        book.execute("SELECT * FROM nothing_here")


def test_many_rows_go_in_at_once(book: Book) -> None:
    book.execute_many(
        "INSERT INTO parent VALUES (?, ?)",
        [("CU-0001", "Saint Brannon"), ("CU-0002", "Halvern Clinic")],
    )
    assert book.value("SELECT count(*) FROM parent") == 2


def test_a_failed_batch_reads_as_a_conflict(book: Book) -> None:
    with pytest.raises(ConflictError):
        book.execute_many(
            "INSERT INTO parent VALUES (?, ?)",
            [("CU-0001", "One"), ("CU-0001", "Again")],
        )


def add_a_parent_then_a_bad_child(book: Book, parent_id: str) -> None:
    with book.atomic():
        book.execute("INSERT INTO parent VALUES (?, ?)", (parent_id, "Saint Brannon"))
        book.execute("INSERT INTO child VALUES (?, ?)", ("X-1", "CU-0404"))


def test_a_savepoint_rolls_the_whole_group_back(book: Book) -> None:
    with pytest.raises(ValidationError):
        add_a_parent_then_a_bad_child(book, "CU-0001")
    assert book.value("SELECT count(*) FROM parent") == 0


def test_savepoints_nest(book: Book) -> None:
    with book.atomic():
        book.execute("INSERT INTO parent VALUES (?, ?)", ("CU-0001", "Saint Brannon"))
        with pytest.raises(ValidationError):
            add_a_parent_then_a_bad_child(book, "CU-0002")
    assert book.value("SELECT count(*) FROM parent") == 1


def test_a_savepoint_that_finishes_keeps_its_writes(book: Book) -> None:
    with book.atomic():
        book.execute("INSERT INTO parent VALUES (?, ?)", ("CU-0001", "Saint Brannon"))
        book.execute("INSERT INTO child VALUES (?, ?)", ("X-1", "CU-0001"))
    assert book.value("SELECT count(*) FROM child") == 1


def test_a_closed_book_refuses_everything(book: Book) -> None:
    book.close()
    assert book.closed
    with pytest.raises(MolycowError, match="closed"):
        book.execute("SELECT 1")
    with pytest.raises(MolycowError, match="closed"):
        book.atomic().__enter__()
    book.close()


def test_a_block_of_sql_is_cut_into_whole_statements() -> None:
    cut = split_statements(SETUP)
    assert len(cut) == 2
    assert cut[0].startswith("CREATE TABLE parent")
    assert cut[1].endswith(";")


def test_a_block_that_stops_mid_statement_is_refused() -> None:
    with pytest.raises(ValidationError, match="part way through"):
        split_statements("CREATE TABLE half (id TEXT")


def test_a_script_runs_inside_a_savepoint_and_can_be_rolled_back(book: Book) -> None:
    with pytest.raises(ValidationError):
        add_a_table_then_fail(book)
    names = {row["name"] for row in book.all("SELECT name FROM sqlite_master")}
    assert "late" not in names


def add_a_table_then_fail(book: Book) -> None:
    with book.atomic():
        book.script("CREATE TABLE late (id TEXT PRIMARY KEY);")
        book.execute("INSERT INTO child VALUES (?, ?)", ("X-9", "CU-0404"))
