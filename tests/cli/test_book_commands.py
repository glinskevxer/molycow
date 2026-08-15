from pathlib import Path

import pytest
from click.testing import CliRunner

from molycow import __version__
from molycow.cli.main import main, run
from molycow.store import Book
from molycow.store.migrations import latest, schema_version


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_the_cli_reports_its_version(runner: CliRunner) -> None:
    result = runner.invoke(run, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_init_makes_a_book_at_the_current_schema(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    result = runner.invoke(run, ["--book", str(target), "book", "init"])
    assert result.exit_code == 0
    assert f"schema {latest()}" in result.output
    with Book.open(target) as opened:
        assert schema_version(opened) == latest()


def test_init_twice_says_it_was_already_there(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "init"])
    assert "already at schema" in result.output


def test_a_command_against_a_book_that_is_not_there_fails(
    runner: CliRunner, tmp_path: Path
) -> None:
    result = runner.invoke(run, ["--book", str(tmp_path / "nope.sqlite3"), "book", "counts"])
    assert result.exit_code != 0
    assert "there is no book" in str(result.exception)


def test_migrate_runs_the_steps_and_says_which(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    with Book.open(target) as opened:
        opened.execute("PRAGMA user_version = 0")
    result = runner.invoke(run, ["--book", str(target), "book", "migrate"])
    assert result.exit_code == 0
    assert "core register" in result.output
    assert f"schema {latest()}" in result.output


def test_migrate_can_stop_part_way(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    with Book.open(target) as opened:
        opened.execute("PRAGMA user_version = 0")
    result = runner.invoke(run, ["--book", str(target), "book", "migrate", "--upto", "2"])
    assert "generator bench" in result.output
    assert "the book is at schema 2" in result.output


def test_migrate_on_a_current_book_does_nothing(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "migrate"])
    assert "nothing to do" in result.output


def test_check_prints_the_schema_and_the_zone(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "check"])
    assert result.exit_code == 0
    assert f"schema   {latest()} of {latest()}" in result.output
    assert "America/Chicago" in result.output


def test_check_fails_on_a_book_behind_the_build(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    with Book.open(target) as opened:
        opened.execute("PRAGMA user_version = 1")
    result = runner.invoke(run, ["--book", str(target), "book", "check"])
    assert result.exit_code != 0


def test_a_command_against_a_stale_book_says_to_migrate(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    with Book.open(target) as opened:
        opened.execute("PRAGMA user_version = 3")
    result = runner.invoke(run, ["--book", str(target), "book", "counts"])
    assert "book migrate" in str(result.exception)


def test_counts_lists_the_tables(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "counts"])
    assert result.exit_code == 0
    assert "possession_limit" in result.output
    assert "customer" in result.output


def test_the_zone_can_be_changed_for_a_run(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "--zone", "UTC", "book", "check"])
    assert "UTC" in result.output


def test_main_turns_our_errors_into_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv", ["molycow", "--book", "/nowhere/at/all.sqlite3", "book", "counts"]
    )
    assert main() == 1


def test_main_returns_zero_on_a_command_that_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "day.sqlite3"
    monkeypatch.setattr("sys.argv", ["molycow", "--book", str(target), "book", "init"])
    assert main() == 0


def test_verify_says_a_fresh_book_is_sound(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "verify"])
    assert result.exit_code == 0
    assert "is sound" in result.output


def test_verify_reports_a_row_pointing_at_nothing(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    with Book.open(target) as opened:
        opened.execute("PRAGMA foreign_keys = OFF")
        opened.execute(
            """
            INSERT INTO authorized_user
              (id, customer_id, name, licence, added_on)
            VALUES ('AU-0001', 'CU-0404', 'R. Okonkwo', '42-28931-01', '2025-01-06')
            """
        )
    result = runner.invoke(run, ["--book", str(target), "book", "verify"])
    assert result.exit_code != 0
    assert "points at a missing customer" in result.output


def test_a_backup_is_written_and_counted(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    copy = tmp_path / "copy.sqlite3"
    result = runner.invoke(run, ["--book", str(target), "book", "backup", str(copy)])
    assert result.exit_code == 0
    assert copy.exists()
    assert "rows" in result.output


def test_the_laws_command_lists_every_rule(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "laws"])
    assert result.exit_code == 0
    assert "eluate-untested" in result.output
    assert "rules" in result.output.splitlines()[-1]


def test_the_laws_can_be_narrowed_to_one_subject(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "laws", "--about", "routes"])
    assert "van-index" in result.output
    assert "eluate-untested" not in result.output


def test_a_subject_nobody_has_rules_about_lists_the_ones_that_exist(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "book", "laws", "--about", "gossip"])
    assert result.exit_code != 0
    assert "try one of" in result.output


def test_the_help_shows_the_worked_example(runner: CliRunner) -> None:
    result = runner.invoke(run, ["--help"])
    assert result.exit_code == 0
    assert "A morning, in the order it happens" in result.output
    assert "molycow report day --on 2025-04-08" in result.output


def test_every_group_shows_up_in_the_help(runner: CliRunner) -> None:
    result = runner.invoke(run, ["--help"])
    for group in ("generator", "kit", "dose", "ship", "route", "waste", "report", "audit"):
        assert group in result.output


def test_a_group_prints_its_own_commands(runner: CliRunner) -> None:
    result = runner.invoke(run, ["kit", "--help"])
    assert "compound" in result.output
    assert "strips" in result.output
    assert "recall" in result.output


def test_about_says_which_build_it_is(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "about"])
    assert result.exit_code == 0
    assert __version__ in result.output
    assert f"schema   {latest()} expected" in result.output


def test_about_says_what_the_book_holds(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "about"])
    assert "tables" in result.output
    assert "rows" in result.output
    assert str(target) in result.output


def test_about_works_before_the_book_exists(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(run, ["--book", str(tmp_path / "nothing.sqlite3"), "about"])
    assert result.exit_code == 0
    assert "not there yet" in result.output


def test_about_counts_the_rules_and_the_tables_it_knows(runner: CliRunner, tmp_path: Path) -> None:
    from molycow.formulary import known as kits
    from molycow.nuclides import known as nuclides
    from molycow.rules import rules

    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    result = runner.invoke(run, ["--book", str(target), "about"])
    assert f"rules    {len(rules())}" in result.output
    assert f"{len(nuclides())} handled" in result.output
    assert f"{len(kits())} kits" in result.output


def test_about_shows_a_book_that_is_behind_the_build(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    with Book.open(target) as opened:
        opened.execute("PRAGMA user_version = 4")
    result = runner.invoke(run, ["--book", str(target), "about"])
    assert result.exit_code == 0
    assert "schema 4," in result.output
