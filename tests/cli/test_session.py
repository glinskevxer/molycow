from pathlib import Path

import pytest

from molycow.cli.session import Session
from molycow.errors import MolycowError
from molycow.store import Book
from molycow.store.migrations import apply, latest, schema_version


def test_a_session_carries_the_zone_it_was_asked_for(tmp_path: Path) -> None:
    session = Session(tmp_path / "day.sqlite3", "UTC")
    assert session.tz.key == "UTC"
    assert session.clock.now().tzinfo is not None


def test_the_default_zone_is_the_pharmacy_zone(tmp_path: Path) -> None:
    assert Session(tmp_path / "day.sqlite3").zone_name == "America/Chicago"


def open_it(session: Session) -> None:
    with session.open():
        pass


def test_a_book_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MolycowError, match="there is no book"):
        open_it(Session(tmp_path / "nothing.sqlite3"))


def test_a_book_behind_the_build_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    with Book.open(target) as book:
        apply(book, upto=2)
    with pytest.raises(MolycowError, match="book migrate"):
        open_it(Session(target))


def test_a_stale_book_can_still_be_opened_to_migrate_it(tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    with Book.open(target) as book:
        apply(book, upto=2)
    with Session(target).open(migrated=False) as book:
        assert schema_version(book) == 2


def test_create_makes_the_file(tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    session = Session(target)
    with session.create() as book:
        apply(book)
    assert target.exists()
    with session.open() as book:
        assert schema_version(book) == latest()
