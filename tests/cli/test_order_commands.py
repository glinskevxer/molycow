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
    runner.invoke(
        run,
        [
            "--book",
            str(target),
            "customer",
            "add",
            "Saint Brannon",
            "--kind",
            "hospital",
            "--licence",
            "42-28931-01",
            "--street",
            "1400 Weir Street",
            "--town",
            "Ardmore",
            "--zone",
            "north",
            "--opened",
            "2025-01-06",
        ],
    )
    runner.invoke(
        run,
        [
            "--book",
            str(target),
            "physician",
            "add",
            "CU-0001",
            "R. Okonkwo",
            "--licence",
            "42-28931-01",
            "--nuclide",
            "Tc-99m",
            "--added",
            "2025-01-06",
        ],
    )
    return target


def call(runner: CliRunner, bookfile: Path, *args: str) -> Result:
    return runner.invoke(run, ["--book", str(bookfile), *args])


def take(runner: CliRunner, bookfile: Path, activity: str = "22 mCi", **extra: str) -> Result:
    args = [
        "order",
        "take",
        extra.get("customer", "CU-0001"),
        "AU-0001",
        "--code",
        "MDP",
        "--procedure",
        "whole body bone",
        "--ref",
        "A-4471902",
        "--activity",
        activity,
        "--calibration",
        extra.get("calibration", "2025-04-08 09:00"),
        "--at",
        "2025-04-07 16:10",
    ]
    return call(runner, bookfile, *args)


def test_an_order_is_taken_and_numbered(runner: CliRunner, bookfile: Path) -> None:
    result = take(runner, bookfile)
    assert result.exit_code == 0
    assert result.output.startswith("ORD-250407-01 CU-0001 MDP 22.0 mCi")


def test_an_order_outside_the_adult_dose_range_is_refused(
    runner: CliRunner, bookfile: Path
) -> None:
    result = take(runner, bookfile, "120 mCi")
    assert result.exit_code != 0
    assert "adult dose" in str(result.exception)


def test_the_desk_can_check_an_order_without_taking_it(runner: CliRunner, bookfile: Path) -> None:
    good = call(
        runner,
        bookfile,
        "order",
        "check",
        "CU-0001",
        "AU-0001",
        "--code",
        "MDP",
        "--activity",
        "22 mCi",
        "--calibration",
        "2025-04-08 09:00",
    )
    assert "would be taken" in good.output
    bad = call(
        runner,
        bookfile,
        "order",
        "check",
        "CU-0001",
        "AU-0001",
        "--code",
        "MAA",
        "--activity",
        "22 mCi",
        "--calibration",
        "2025-04-08 09:00",
    )
    assert "refused [dose-range]" in bad.output
    assert "no orders" in call(runner, bookfile, "order", "list").output


def test_the_order_list_reads_back(runner: CliRunner, bookfile: Path) -> None:
    take(runner, bookfile)
    listed = call(runner, bookfile, "order", "list")
    assert "ORD-250407-01" in listed.output
    assert "A-4471902" in listed.output
    assert "open" in listed.output


def test_the_list_narrows_by_day_and_customer(runner: CliRunner, bookfile: Path) -> None:
    take(runner, bookfile)
    assert "ORD-250407-01" in call(runner, bookfile, "order", "list", "--on", "2025-04-08").output
    assert "no orders" in call(runner, bookfile, "order", "list", "--on", "2025-04-09").output
    assert (
        "ORD-250407-01" in call(runner, bookfile, "order", "list", "--customer", "CU-0001").output
    )


def test_the_worklist_is_the_next_few_hours(runner: CliRunner, bookfile: Path) -> None:
    take(runner, bookfile)
    take(runner, bookfile, calibration="2025-04-08 15:00")
    soon = call(runner, bookfile, "order", "worklist", "--at", "2025-04-08 06:30")
    assert soon.output.count("ORD-") == 1
    wide = call(runner, bookfile, "order", "worklist", "--at", "2025-04-08 06:30", "--hours", "12")
    assert wide.output.count("ORD-") == 2


def test_an_empty_worklist_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert (
        "nothing due"
        in call(runner, bookfile, "order", "worklist", "--at", "2025-04-08 06:30").output
    )


def test_a_late_order_is_named(runner: CliRunner, bookfile: Path) -> None:
    take(runner, bookfile)
    assert (
        "nothing is late"
        in call(runner, bookfile, "order", "late", "--at", "2025-04-08 07:00").output
    )
    late = call(runner, bookfile, "order", "late", "--at", "2025-04-08 10:00")
    assert "ORD-250407-01" in late.output


def test_cancelling_takes_an_order_off_the_open_list(runner: CliRunner, bookfile: Path) -> None:
    take(runner, bookfile)
    assert "cancelled" in call(runner, bookfile, "order", "cancel", "ORD-250407-01").output
    assert "no orders" in call(runner, bookfile, "order", "list", "--open").output
    assert "cancelled" in call(runner, bookfile, "order", "list").output


def test_cancelling_twice_is_refused(runner: CliRunner, bookfile: Path) -> None:
    take(runner, bookfile)
    call(runner, bookfile, "order", "cancel", "ORD-250407-01")
    again = call(runner, bookfile, "order", "cancel", "ORD-250407-01")
    assert again.exit_code != 0
    assert "already been finished" in str(again.exception)


def test_a_stat_order_is_marked_on_the_worklist(runner: CliRunner, bookfile: Path) -> None:
    call(
        runner,
        bookfile,
        "order",
        "take",
        "CU-0001",
        "AU-0001",
        "--code",
        "MDP",
        "--procedure",
        "lung scan",
        "--ref",
        "A-4471999",
        "--activity",
        "22 mCi",
        "--calibration",
        "2025-04-08 15:00",
        "--at",
        "2025-04-07 16:10",
        "--stat",
    )
    take(runner, bookfile)
    worklist = call(runner, bookfile, "order", "worklist", "--at", "2025-04-08 06:30")
    assert worklist.output.splitlines()[0].startswith("STAT")


def test_an_order_with_no_notice_has_to_be_marked_stat(runner: CliRunner, bookfile: Path) -> None:
    refused = call(
        runner,
        bookfile,
        "order",
        "take",
        "CU-0001",
        "AU-0001",
        "--code",
        "MDP",
        "--procedure",
        "lung scan",
        "--ref",
        "A-4471999",
        "--activity",
        "22 mCi",
        "--calibration",
        "2025-04-08 09:00",
        "--at",
        "2025-04-08 08:40",
    )
    assert refused.exit_code != 0
    assert "mark it stat" in str(refused.exception)
    taken = call(
        runner,
        bookfile,
        "order",
        "take",
        "CU-0001",
        "AU-0001",
        "--code",
        "MDP",
        "--procedure",
        "lung scan",
        "--ref",
        "A-4471999",
        "--activity",
        "22 mCi",
        "--calibration",
        "2025-04-08 09:00",
        "--at",
        "2025-04-08 08:40",
        "--stat",
    )
    assert taken.exit_code == 0
