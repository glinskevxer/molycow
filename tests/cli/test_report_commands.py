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


def test_the_day_sheet_prints_whole(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "day", "--on", "2025-04-08")
    assert "hot lab day sheet 2025-04-08" in result.output
    assert "elutions" in result.output
    assert "DS-250408-01" in result.output


def test_one_section_can_be_asked_for(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "day", "--on", "2025-04-08", "--section", "doses")
    assert result.output.startswith("doses")
    assert "elutions" not in result.output


def test_a_section_that_does_not_exist_lists_the_ones_that_do(
    runner: CliRunner, bookfile: Path
) -> None:
    result = call(runner, bookfile, "report", "day", "--on", "2025-04-08", "--section", "gossip")
    assert result.exit_code != 0
    assert "elutions" in result.output


def test_an_empty_day_still_prints_a_sheet(runner: CliRunner, tmp_path: Path) -> None:
    target = a_book(runner, tmp_path)
    result = call(runner, target, "report", "day", "--on", "2025-04-08")
    assert "no column was milked" in result.output


def test_the_holdings_read_against_the_licence(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "holdings", "--at", "2025-04-08 08:00")
    assert "Mo-99" in result.output
    assert "% of limit" in result.output
    assert "OVER" not in result.output


def test_the_holdings_can_be_broken_down_by_place(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "holdings", "--at", "2025-04-08 08:00", "--place")
    assert "generators" in result.output
    assert "eluate" in result.output


def test_an_empty_building_says_so(runner: CliRunner, tmp_path: Path) -> None:
    target = a_book(runner, tmp_path)
    result = call(runner, target, "report", "holdings", "--at", "2025-04-08 08:00")
    assert "nothing on the premises" in result.output


def test_the_licence_prints_its_limits(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "licence")
    assert "Tc-99m 20.0 Ci" in result.output
    assert "generators on the bench" in result.output


def test_the_room_left_under_a_limit(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "room", "Mo-99", "--at", "2025-04-08 08:00")
    assert "holding" in result.output
    assert "room for" in result.output


def test_a_nuclide_the_licence_does_not_name(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "report", "room", "Y-90", "--at", "2025-04-08 08:00")
    assert result.exit_code != 0
    assert "does not name" in str(result.exception)
