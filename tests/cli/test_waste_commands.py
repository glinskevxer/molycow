from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from tests.cli.support import a_book, a_working_morning, call


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    target = a_book(runner, tmp_path)
    call(runner, target, "waste", "open", "--kind", "vials", "--at", "2025-04-08 06:00")
    return target


def discard(runner: CliRunner, bookfile: Path, nuclide: str = "Tc-99m") -> Result:
    return call(
        runner,
        bookfile,
        "waste",
        "discard",
        "WC-0001",
        "--nuclide",
        nuclide,
        "--activity",
        "40 mCi",
        "--at",
        "2025-04-08 10:30",
        "--from",
        "EL-250408-01",
    )


def test_a_container_is_opened_and_numbered(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "waste", "open", "--kind", "sharps", "--at", "2025-04-08 06:00")
    assert "WC-0002 sharps opened" in result.output


def test_something_dropped_in_says_when_it_clears(runner: CliRunner, bookfile: Path) -> None:
    result = discard(runner, bookfile)
    assert "holds 1 items" in result.output
    assert "clear 2025-04-10" in result.output


def test_a_long_lived_nuclide_pushes_the_clear_date_out(runner: CliRunner, bookfile: Path) -> None:
    result = discard(runner, bookfile, "I-131")
    assert "clear 2025-0" in result.output
    assert "clear 2025-04" not in result.output


def test_an_unused_syringe_goes_in_at_what_it_reads(runner: CliRunner, tmp_path: Path) -> None:
    target = a_working_morning(runner, tmp_path)
    call(runner, target, "waste", "open", "--kind", "sharps", "--at", "2025-04-08 06:00")
    result = call(
        runner, target, "waste", "dose", "WC-0001", "DS-250408-01", "--at", "2025-04-08 16:00"
    )
    assert "took DS-250408-01" in result.output


def test_the_store_says_why_a_drum_is_still_there(runner: CliRunner, bookfile: Path) -> None:
    discard(runner, bookfile)
    open_store = call(runner, bookfile, "waste", "store", "--at", "2025-04-08 17:00")
    assert "still open" in open_store.output
    call(runner, bookfile, "waste", "close", "WC-0001", "--at", "2025-04-08 17:00")
    closed = call(runner, bookfile, "waste", "store", "--at", "2025-04-09 09:00")
    assert "not held ten half lives yet" in closed.output


def test_an_untouched_drum_reads_as_holding_nothing(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "waste", "store", "--at", "2025-04-08 17:00")
    assert "nothing has gone in it" in result.output
    assert "store holding 0.00 mCi" in result.output


def test_a_drum_cannot_go_out_early(runner: CliRunner, bookfile: Path) -> None:
    discard(runner, bookfile)
    call(runner, bookfile, "waste", "close", "WC-0001", "--at", "2025-04-08 17:00")
    result = call(
        runner,
        bookfile,
        "waste",
        "dispose",
        "WC-0001",
        "--at",
        "2025-04-09 09:00",
        "--by",
        "K. Ruzicka",
        "--survey",
        "0.01",
    )
    assert result.exit_code != 0
    assert "not held ten half lives" in str(result.exception)


def test_a_drum_that_reads_above_background_stays(runner: CliRunner, bookfile: Path) -> None:
    discard(runner, bookfile)
    call(runner, bookfile, "waste", "close", "WC-0001", "--at", "2025-04-08 17:00")
    result = call(
        runner,
        bookfile,
        "waste",
        "dispose",
        "WC-0001",
        "--at",
        "2025-04-12 09:00",
        "--by",
        "K. Ruzicka",
        "--survey",
        "0.4",
    )
    assert result.exit_code != 0
    assert "background" in str(result.exception)


def test_a_held_drum_goes_out_once_both_agree(runner: CliRunner, bookfile: Path) -> None:
    discard(runner, bookfile)
    call(runner, bookfile, "waste", "close", "WC-0001", "--at", "2025-04-08 17:00")
    ready = call(runner, bookfile, "waste", "store", "--at", "2025-04-12 09:00")
    assert "ready to survey out" in ready.output
    result = call(
        runner,
        bookfile,
        "waste",
        "dispose",
        "WC-0001",
        "--at",
        "2025-04-12 09:00",
        "--by",
        "K. Ruzicka",
        "--survey",
        "0.01",
    )
    assert "disposed 2025-04-12" in result.output
    assert (
        "the store is empty"
        in call(runner, bookfile, "waste", "store", "--at", "2025-04-12 10:00").output
    )


def test_a_container_can_be_looked_into(runner: CliRunner, bookfile: Path) -> None:
    assert "nothing has gone in it" in call(runner, bookfile, "waste", "show", "WC-0001").output
    discard(runner, bookfile)
    result = call(runner, bookfile, "waste", "show", "WC-0001")
    assert "EL-250408-01" in result.output
    assert "Tc-99m" in result.output
