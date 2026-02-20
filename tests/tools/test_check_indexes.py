from molycow.store import Book
from molycow.store.migrations import apply
from molycow.tools import check_indexes


def test_every_foreign_key_has_an_index_behind_it() -> None:
    assert check_indexes.findings() == []
    assert check_indexes.main() == 0


def test_a_primary_key_column_counts_as_covered() -> None:
    with Book.in_memory() as book:
        apply(book)
        covered = check_indexes.covered_columns(book, "customer")
        assert "id" in covered


def test_an_index_covers_its_leading_column(book: Book) -> None:
    covered = check_indexes.covered_columns(book, "customer_order")
    assert "customer_id" in covered
    assert "calibration_at" in covered


def test_the_check_reads_a_book_it_built_itself() -> None:
    assert check_indexes.MIGRATIONS_FILE.name == "migrations.py"
    assert check_indexes.MIGRATIONS_FILE.exists()


def test_the_child_side_of_every_key_is_indexed(book: Book) -> None:
    for table in book.tables():
        covered = check_indexes.covered_columns(book, table)
        for key in book.all(f"PRAGMA foreign_key_list({table})"):
            if int(key["seq"]) == 0:
                assert str(key["from"]) in covered
