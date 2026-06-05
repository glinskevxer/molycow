from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from tests.cli.support import a_book, call


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    return a_book(runner, tmp_path)


def record(runner: CliRunner, bookfile: Path, person: str, deep: str) -> Result:
    return call(
        runner,
        bookfile,
        "badge",
        "record",
        person,
        "2025Q2",
        "--deep",
        deep,
        "--extremity",
        "1400",
        "--read",
        "2025-07-14",
    )


def test_a_badge_reading_is_written_down(runner: CliRunner, bookfile: Path) -> None:
    result = record(runner, bookfile, "K. Ruzicka", "120")
    assert "2025Q2  K. Ruzicka" in result.output
    assert "deep     120 mrem" in result.output


def test_a_quarter_nobody_has_sent_back(runner: CliRunner, bookfile: Path) -> None:
    assert "no badges have come back" in call(runner, bookfile, "badge", "quarter", "2025Q2").output


def test_the_quarter_lists_everybody_and_names_who_is_missing(
    runner: CliRunner, bookfile: Path
) -> None:
    record(runner, bookfile, "K. Ruzicka", "120")
    call(
        runner,
        bookfile,
        "badge",
        "record",
        "P. Vantrease",
        "2025Q1",
        "--deep",
        "90",
        "--extremity",
        "900",
        "--read",
        "2025-04-14",
    )
    result = call(runner, bookfile, "badge", "quarter", "2025Q2")
    assert "K. Ruzicka" in result.output
    assert "no reading yet for: P. Vantrease" in result.output


def test_a_quarter_that_is_read_twice_is_refused(runner: CliRunner, bookfile: Path) -> None:
    record(runner, bookfile, "K. Ruzicka", "120")
    again = record(runner, bookfile, "K. Ruzicka", "130")
    assert again.exit_code != 0
    assert "already been read" in str(again.exception)


def test_one_persons_year_prints_the_share_used(runner: CliRunner, bookfile: Path) -> None:
    record(runner, bookfile, "K. Ruzicka", "120")
    result = call(runner, bookfile, "badge", "year", "2025", "--person", "K. Ruzicka")
    assert "% of the year" in result.output


def test_a_quiet_year_leaves_nobody_on_the_watch_list(runner: CliRunner, bookfile: Path) -> None:
    record(runner, bookfile, "K. Ruzicka", "120")
    assert "nobody is near their limit" in call(runner, bookfile, "badge", "year", "2025").output


def test_a_busy_year_puts_somebody_on_the_watch_list(runner: CliRunner, bookfile: Path) -> None:
    record(runner, bookfile, "P. Vantrease", "5200")
    result = call(runner, bookfile, "badge", "year", "2025")
    assert "OVER THE LIMIT" in result.output
    assert "P. Vantrease" in result.output
