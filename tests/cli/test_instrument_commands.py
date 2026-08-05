from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from tests.cli.support import a_book, call


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    target = a_book(runner, tmp_path)
    call(
        runner,
        target,
        "instrument",
        "add",
        "551-40922",
        "--kind",
        "dose calibrator",
        "--maker",
        "Vernay",
        "--model",
        "CRC-55tR",
        "--installed",
        "2023-06-12",
        "--calibrated",
        "2025-02-03",
    )
    call(
        runner,
        target,
        "instrument",
        "source",
        "CS-9912",
        "--nuclide",
        "Cs-137",
        "--activity",
        "200 uCi",
        "--certified",
        "2019-07-01",
    )
    return target


def expected_reading(runner: CliRunner, bookfile: Path) -> str:
    listed = call(runner, bookfile, "instrument", "sources", "--on", "2025-04-08")
    return listed.output.split("reads")[1].split("uCi")[0].strip() + " uCi"


def check(runner: CliRunner, bookfile: Path, reading: str) -> Result:
    return call(
        runner,
        bookfile,
        "instrument",
        "check",
        "IC-0001",
        "CS-9912",
        "--at",
        "2025-04-08 06:05",
        "--read",
        reading,
        "--by",
        "K. Ruzicka",
    )


def test_an_instrument_is_booked_in_with_its_due_date(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "instrument", "list")
    assert "IC-0001" in result.output
    assert "calibration due 2026-02-03" in result.output


def test_an_instrument_out_of_calibration_drops_off_the_usable_list(
    runner: CliRunner, bookfile: Path
) -> None:
    assert "IC-0001" in call(runner, bookfile, "instrument", "list", "--on", "2025-04-08").output
    assert (
        "no instruments"
        in call(runner, bookfile, "instrument", "list", "--on", "2026-06-01").output
    )


def test_a_sealed_source_reads_down_from_its_certificate(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "instrument", "sources", "--on", "2025-04-08")
    assert "CS-9912" in result.output
    assert "certified 200.0 uCi" in result.output
    assert "reads 1" in result.output


def test_a_check_prints_the_verdict_and_what_was_expected(
    runner: CliRunner, bookfile: Path
) -> None:
    result = check(runner, bookfile, expected_reading(runner, bookfile))
    assert "constancy passed" in result.output
    assert "expected" in result.output


def test_a_check_a_long_way_off_fails(runner: CliRunner, bookfile: Path) -> None:
    result = check(runner, bookfile, "80 uCi")
    assert "constancy FAILED" in result.output


def test_a_check_on_an_uncalibrated_instrument_is_refused(
    runner: CliRunner, bookfile: Path
) -> None:
    call(
        runner,
        bookfile,
        "instrument",
        "add",
        "551-00001",
        "--kind",
        "survey meter",
        "--maker",
        "Vernay",
        "--model",
        "451P",
        "--installed",
        "2020-01-06",
        "--calibrated",
        "2020-01-06",
    )
    result = call(
        runner,
        bookfile,
        "instrument",
        "check",
        "IC-0002",
        "CS-9912",
        "--at",
        "2025-04-08 06:05",
        "--read",
        "150 uCi",
        "--by",
        "K. Ruzicka",
    )
    assert result.exit_code != 0
    assert "calibration has run out" in str(result.exception)


def test_everything_is_overdue_until_it_has_been_run(runner: CliRunner, bookfile: Path) -> None:
    due = call(runner, bookfile, "instrument", "due", "IC-0001", "--on", "2025-04-08")
    assert "constancy overdue" in due.output
    check(runner, bookfile, expected_reading(runner, bookfile))
    after = call(runner, bookfile, "instrument", "due", "IC-0001", "--on", "2025-04-08")
    assert "constancy overdue" not in after.output


def test_the_history_reads_back(runner: CliRunner, bookfile: Path) -> None:
    assert "no checks" in call(runner, bookfile, "instrument", "history", "IC-0001").output
    check(runner, bookfile, expected_reading(runner, bookfile))
    history = call(runner, bookfile, "instrument", "history", "IC-0001", "--kind", "constancy")
    assert "CS-9912" in history.output


def test_a_linearity_run_prints_every_point(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "instrument",
        "linearity",
        "IC-0001",
        "--read",
        "2025-04-08 07:00",
        "400 mCi",
        "--read",
        "2025-04-08 13:00",
        "200.1 mCi",
        "--read",
        "2025-04-09 07:00",
        "25.2 mCi",
        "--by",
        "K. Ruzicka",
    )
    assert "linearity passed" in result.output
    assert result.output.count("%") >= 4


def test_a_calibrator_that_reads_low_at_the_bottom_fails_linearity(
    runner: CliRunner, bookfile: Path
) -> None:
    result = call(
        runner,
        bookfile,
        "instrument",
        "linearity",
        "IC-0001",
        "--read",
        "2025-04-08 07:00",
        "400 mCi",
        "--read",
        "2025-04-08 13:00",
        "200.1 mCi",
        "--read",
        "2025-04-10 07:00",
        "1.35 mCi",
        "--by",
        "K. Ruzicka",
    )
    assert "linearity FAILED" in result.output


def test_the_board_prints_for_a_day(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "instrument", "board", "--on", "2025-04-08")
    assert "instruments 2025-04-08" in result.output
    assert "IC-0001" in result.output
    assert "overdue" in result.output
