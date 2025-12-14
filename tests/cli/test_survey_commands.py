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


def walk(runner: CliRunner, bookfile: Path, counts: str = "340") -> Result:
    return call(
        runner,
        bookfile,
        "survey",
        "walk",
        "--at",
        "2025-04-08 17:40",
        "--by",
        "K. Ruzicka",
        "--read",
        "hot lab",
        "1.2",
        "--read",
        "dispensing bench",
        "0.8",
        "--read",
        "packaging",
        "0.3",
        "--read",
        "waste store",
        "2.1",
        "--wipe",
        "hot lab",
        "draw station",
        counts,
        "120",
    )


def test_a_walk_is_written_down(runner: CliRunner, bookfile: Path) -> None:
    result = walk(runner, bookfile)
    assert "SV-250408-01 4 readings 1 wipes" in result.output
    assert "FAILED" not in result.output


def test_a_dirty_wipe_fails_the_walk(runner: CliRunner, bookfile: Path) -> None:
    result = walk(runner, bookfile, "4000")
    assert "FAILED" in result.output
    assert "draw station wiped" in result.output


def test_a_hot_public_area_fails_the_walk(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "survey",
        "walk",
        "--at",
        "2025-04-08 17:40",
        "--by",
        "K. Ruzicka",
        "--read",
        "reception",
        "0.4",
    )
    assert "FAILED: reception reading 0.40 mrem/h" in result.output


def test_the_day_says_what_was_missed(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "survey",
        "walk",
        "--at",
        "2025-04-08 17:40",
        "--by",
        "K. Ruzicka",
        "--read",
        "hot lab",
        "1.2",
    )
    assert result.exit_code == 0
    day = call(runner, bookfile, "survey", "day", "--on", "2025-04-08")
    assert "not surveyed:" in day.output
    assert "dispensing bench" in day.output


def test_a_full_walk_leaves_nothing_missed(runner: CliRunner, bookfile: Path) -> None:
    walk(runner, bookfile)
    day = call(runner, bookfile, "survey", "day", "--on", "2025-04-08")
    assert "not surveyed" not in day.output
    assert "hottest waste store 2.10 mrem/h" in day.output
    assert "clean" in day.output


def test_a_day_nobody_walked(runner: CliRunner, bookfile: Path) -> None:
    assert (
        "nobody walked the building"
        in call(runner, bookfile, "survey", "day", "--on", "2025-04-08").output
    )


def test_a_dirty_spot_stays_open_until_it_is_wiped_clean(runner: CliRunner, bookfile: Path) -> None:
    walk(runner, bookfile, "4000")
    assert "draw station" in call(runner, bookfile, "survey", "open").output
    call(
        runner,
        bookfile,
        "survey",
        "walk",
        "--at",
        "2025-04-08 18:20",
        "--by",
        "K. Ruzicka",
        "--wipe",
        "hot lab",
        "draw station",
        "200",
        "120",
    )
    assert "nothing is open" in call(runner, bookfile, "survey", "open").output


def test_a_tighter_limit_reopens_a_spot(runner: CliRunner, bookfile: Path) -> None:
    walk(runner, bookfile, "600")
    assert "nothing is open" in call(runner, bookfile, "survey", "open").output
    assert "draw station" in call(runner, bookfile, "survey", "open", "--limit", "200").output


def test_the_areas_and_their_limits_print(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "survey", "areas")
    assert "hot lab" in result.output
    assert "reception" in result.output
    assert "0.05 mrem/h" in result.output
