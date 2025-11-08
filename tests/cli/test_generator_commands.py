from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from molycow.cli.main import run


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    return target


def call(runner: CliRunner, bookfile: Path, *args: str) -> Result:
    return runner.invoke(run, ["--book", str(bookfile), *args])


def receive(runner: CliRunner, bookfile: Path, activity: str = "2 Ci") -> Result:
    return call(
        runner,
        bookfile,
        "generator",
        "receive",
        "M99-44182",
        "--maker",
        "Corren Isotopes",
        "--activity",
        activity,
        "--calibrated",
        "2025-04-05 12:00",
        "--received",
        "2025-04-05",
        "--expires",
        "2025-04-19",
    )


def milk(runner: CliRunner, bookfile: Path, activity: str = "940 mCi") -> Result:
    return call(
        runner,
        bookfile,
        "generator",
        "milk",
        "GEN-0001",
        "--at",
        "2025-04-08 06:30",
        "--volume",
        "10 mL",
        "--activity",
        activity,
    )


def test_a_column_is_booked_in(runner: CliRunner, bookfile: Path) -> None:
    result = receive(runner, bookfile)
    assert result.exit_code == 0
    assert result.output.startswith("GEN-0001 M99-44182 2.00 Ci")


def test_a_column_over_the_possession_limit_is_refused(runner: CliRunner, bookfile: Path) -> None:
    result = receive(runner, bookfile, "40 Ci")
    assert result.exit_code != 0
    assert "possession limit" in str(result.exception)


def test_the_bench_lists_what_is_in_date(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    assert "GEN-0001" in call(runner, bookfile, "generator", "list").output
    assert "GEN-0001" in call(runner, bookfile, "generator", "list", "--on", "2025-04-08").output
    assert "no columns" in call(runner, bookfile, "generator", "list", "--on", "2025-04-30").output


def test_an_empty_bench_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert "no columns" in call(runner, bookfile, "generator", "list").output


def test_the_bench_says_what_a_column_should_give(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    result = call(runner, bookfile, "generator", "expect", "GEN-0001", "--at", "2025-04-08 06:30")
    assert "should give" in result.output
    assert "mCi" in result.output


def test_milking_writes_the_elution_and_reports_the_yield(
    runner: CliRunner, bookfile: Path
) -> None:
    receive(runner, bookfile)
    result = milk(runner, bookfile)
    assert result.exit_code == 0
    assert "EL-250408-01" in result.output
    assert "% of expected" in result.output


def test_a_poor_yield_is_refused_until_it_is_forced(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    refused = milk(runner, bookfile, "100 mCi")
    assert refused.exit_code != 0
    forced = call(
        runner,
        bookfile,
        "generator",
        "milk",
        "GEN-0001",
        "--at",
        "2025-04-08 06:30",
        "--volume",
        "10 mL",
        "--activity",
        "100 mCi",
        "--force",
    )
    assert "poor yield" in forced.output


def test_a_clean_breakthrough_test_releases_the_vial(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    milk(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "generator",
        "test",
        "EL-250408-01",
        "--at",
        "2025-04-08 06:45",
        "--moly",
        "0.9 uCi",
        "--aluminium",
        "4",
        "--by",
        "K. Ruzicka",
    )
    assert "passed at" in result.output
    assert "shelf life" in result.output


def test_a_dirty_vial_says_what_failed(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    milk(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "generator",
        "test",
        "EL-250408-01",
        "--at",
        "2025-04-08 06:45",
        "--moly",
        "400 uCi",
        "--aluminium",
        "4",
        "--by",
        "K. Ruzicka",
    )
    assert "FAILED" in result.output
    assert "molybdenum" in result.output


def test_the_eluate_list_says_which_vials_are_released(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    milk(runner, bookfile)
    held = call(runner, bookfile, "generator", "eluates", "--at", "2025-04-08 08:00")
    assert "held" in held.output
    call(
        runner,
        bookfile,
        "generator",
        "test",
        "EL-250408-01",
        "--at",
        "2025-04-08 06:45",
        "--moly",
        "0.9 uCi",
        "--aluminium",
        "4",
        "--by",
        "K. Ruzicka",
    )
    released = call(runner, bookfile, "generator", "eluates", "--at", "2025-04-08 08:00")
    assert "released" in released.output
    assert (
        "nothing in date"
        in call(runner, bookfile, "generator", "eluates", "--at", "2025-04-09 08:00").output
    )


def test_the_elution_log_reads_by_day(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    milk(runner, bookfile)
    assert "EL-250408-01" in call(runner, bookfile, "generator", "log").output
    assert "EL-250408-01" in call(runner, bookfile, "generator", "log", "--on", "2025-04-08").output
    assert "no elutions" in call(runner, bookfile, "generator", "log", "--on", "2025-04-09").output


def test_retiring_a_column_takes_it_off_the_in_date_list(runner: CliRunner, bookfile: Path) -> None:
    receive(runner, bookfile)
    call(runner, bookfile, "generator", "retire", "GEN-0001", "--on", "2025-04-10")
    listed = call(runner, bookfile, "generator", "list", "--on", "2025-04-11")
    assert "no columns" in listed.output
