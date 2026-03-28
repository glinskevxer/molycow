from pathlib import Path

from molycow.tools import smoke


def test_a_morning_runs_end_to_end() -> None:
    assert smoke.main(["--quiet"]) == 0


def test_every_step_is_a_command(tmp_path: Path) -> None:
    results = smoke.drive(tmp_path / "smoke.sqlite3", quiet=True)
    assert len(results) == len(smoke.STEPS)
    assert all(one.exit_code == 0 for one in results)


def test_the_book_is_left_behind_with_the_days_work_in_it(tmp_path: Path) -> None:
    book = tmp_path / "smoke.sqlite3"
    smoke.drive(book, quiet=True)
    from molycow.store import Book

    with Book.open(book) as opened:
        assert opened.row_count("dose") == 1
        assert opened.row_count("shipment") == 1
        assert opened.row_count("survey") == 1


def test_the_run_stops_at_the_first_refusal(tmp_path: Path) -> None:
    book = tmp_path / "smoke.sqlite3"
    original = smoke.STEPS
    smoke.STEPS = (("book", "init"), ("customer", "add"), ("book", "counts"))
    try:
        results = smoke.drive(book, quiet=True)
        assert len(results) == 2
        assert results[-1].exit_code != 0
    finally:
        smoke.STEPS = original


def test_the_things_it_looks_for_are_the_ones_that_matter() -> None:
    assert "DS-250408-01" in smoke.EXPECTED
    assert "hot lab day sheet 2025-04-08" in smoke.EXPECTED
