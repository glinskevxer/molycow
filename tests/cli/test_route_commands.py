from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from tests.cli.support import a_working_morning, call


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    target = a_working_morning(runner, tmp_path)
    call(
        runner,
        target,
        "ship",
        "pack",
        "CU-0001",
        "DS-250408-01",
        "--at",
        "2025-04-08 08:20",
        "--by",
        "K. Ruzicka",
        "--surface",
        "12",
        "--metre",
        "0.35",
    )
    return target


def a_route(runner: CliRunner, bookfile: Path) -> Result:
    return call(
        runner,
        bookfile,
        "route",
        "add",
        "north morning",
        "--zone",
        "north",
        "--leaves",
        "0630",
        "--stop",
        "CU-0001",
    )


def test_a_standing_run_is_set_up(runner: CliRunner, bookfile: Path) -> None:
    result = a_route(runner, bookfile)
    assert result.output.startswith("RT-0001 north morning north leaves 06:30 1 stops")
    assert "CU-0001" in call(runner, bookfile, "route", "list").output


def test_an_empty_route_book_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert "no routes" in call(runner, bookfile, "route", "list").output


def test_the_list_narrows_by_zone(runner: CliRunner, bookfile: Path) -> None:
    a_route(runner, bookfile)
    assert "RT-0001" in call(runner, bookfile, "route", "list", "--zone", "north").output
    assert "no routes" in call(runner, bookfile, "route", "list", "--zone", "river").output


def test_a_box_waits_for_the_run_that_calls_at_its_customer(
    runner: CliRunner, bookfile: Path
) -> None:
    a_route(runner, bookfile)
    result = call(runner, bookfile, "route", "waiting", "RT-0001")
    assert "SH-250408-01" in result.output


def test_a_run_is_opened_loaded_and_sent_out(runner: CliRunner, bookfile: Path) -> None:
    a_route(runner, bookfile)
    opened = call(
        runner,
        bookfile,
        "route",
        "open",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--driver",
        "J. Fennimore",
    )
    assert "driver J. Fennimore" in opened.output
    loaded = call(
        runner, bookfile, "route", "load", "RT-0001", "SH-250408-01", "--on", "2025-04-08"
    )
    assert "carrying 1 boxes, index 0.4" in loaded.output
    left = call(
        runner,
        bookfile,
        "route",
        "depart",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 08:40",
    )
    assert "left at 2025-04-08 08:40" in left.output


def test_an_empty_van_does_not_leave(runner: CliRunner, bookfile: Path) -> None:
    a_route(runner, bookfile)
    call(
        runner,
        bookfile,
        "route",
        "open",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--driver",
        "J. Fennimore",
    )
    result = call(
        runner,
        bookfile,
        "route",
        "depart",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 08:40",
    )
    assert result.exit_code != 0
    assert "nothing on that run" in str(result.exception)


def test_a_box_is_signed_for_on_the_run_and_the_van_comes_back(
    runner: CliRunner, bookfile: Path
) -> None:
    a_route(runner, bookfile)
    call(
        runner,
        bookfile,
        "route",
        "open",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--driver",
        "J. Fennimore",
    )
    call(runner, bookfile, "route", "load", "RT-0001", "SH-250408-01", "--on", "2025-04-08")
    call(
        runner,
        bookfile,
        "route",
        "depart",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 08:40",
    )
    signed = call(
        runner,
        bookfile,
        "route",
        "deliver",
        "RT-0001",
        "SH-250408-01",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 09:05",
        "--to",
        "Reception",
    )
    assert "signed by Reception" in signed.output
    back = call(
        runner,
        bookfile,
        "route",
        "back",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 09:50",
    )
    assert "back at" in back.output
    assert "undelivered" not in back.output


def test_a_box_that_comes_back_undelivered_is_named(runner: CliRunner, bookfile: Path) -> None:
    a_route(runner, bookfile)
    call(
        runner,
        bookfile,
        "route",
        "open",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--driver",
        "J. Fennimore",
    )
    call(runner, bookfile, "route", "load", "RT-0001", "SH-250408-01", "--on", "2025-04-08")
    call(
        runner,
        bookfile,
        "route",
        "depart",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 08:40",
    )
    back = call(
        runner,
        bookfile,
        "route",
        "back",
        "RT-0001",
        "--on",
        "2025-04-08",
        "--at",
        "2025-04-08 09:50",
    )
    assert "SH-250408-01 came back undelivered" in back.output
