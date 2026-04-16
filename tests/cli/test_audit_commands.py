from pathlib import Path

import pytest
from click.testing import CliRunner
from tests.cli.support import a_book, a_working_morning, call


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    return a_working_morning(runner, tmp_path)


def test_the_days_work_reads_back_in_order(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "audit", "day", "--on", "2025-04-08")
    assert "milked" in result.output
    assert "compounded" in result.output
    assert "drew" in result.output


def test_a_quiet_day_says_so(runner: CliRunner, tmp_path: Path) -> None:
    target = a_book(runner, tmp_path)
    assert "nothing was done" in call(runner, target, "audit", "day", "--on", "2025-04-08").output


def test_the_day_can_be_narrowed_to_one_person(runner: CliRunner, bookfile: Path) -> None:
    mine = call(runner, bookfile, "audit", "day", "--on", "2025-04-08", "--actor", "K. Ruzicka")
    assert "drew" in mine.output
    assert "milked" not in mine.output
    nobody = call(runner, bookfile, "audit", "day", "--on", "2025-04-08", "--actor", "Nobody")
    assert "nothing was done" in nobody.output


def test_one_record_carries_its_own_history(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "audit", "record", "EL-250408-01")
    assert "milked" in result.output
    assert "tested" in result.output
    assert "compounded" not in result.output


def test_a_record_nothing_has_happened_to(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "audit", "record", "EL-250409-01")
    assert "nothing has been done" in result.output


def test_one_person_and_their_count(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "audit", "person", "K. Ruzicka")
    assert "entries" in result.output
    assert "drew" in result.output


def test_a_name_that_has_done_nothing(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "audit", "person", "P. Vantrease")
    assert "has done nothing" in result.output


def test_the_milking_can_name_who_did_it(runner: CliRunner, tmp_path: Path) -> None:
    target = a_book(runner, tmp_path)
    call(
        runner,
        target,
        "generator",
        "receive",
        "M99-44182",
        "--maker",
        "Corren Isotopes",
        "--activity",
        "2 Ci",
        "--calibrated",
        "2025-04-05 12:00",
        "--received",
        "2025-04-05",
        "--expires",
        "2025-04-19",
    )
    call(
        runner,
        target,
        "generator",
        "milk",
        "GEN-0001",
        "--at",
        "2025-04-08 06:30",
        "--volume",
        "10 mL",
        "--activity",
        "940 mCi",
        "--by",
        "P. Vantrease",
    )
    assert "P. Vantrease" in call(runner, target, "audit", "record", "EL-250408-01").output
