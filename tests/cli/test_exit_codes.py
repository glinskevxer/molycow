"""The exit codes are a promise to whatever is driving the command line.

A script that fills a morning's orders needs to tell a typo apart from a rule
it is not allowed to break, and the only thing it has to go on is the status.
These drive real refusals through ``main`` rather than asserting against the
class attributes, because the number that matters is the one the shell sees.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from tests.cli.support import a_book, a_working_morning

from molycow.cli.main import main
from molycow.errors import (
    ConflictError,
    MolycowError,
    NotFoundError,
    ReleaseError,
    RuleError,
    SafetyError,
    ValidationError,
)


def run_argv(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr("sys.argv", ["molycow", *args])
    return main()


def test_a_book_that_is_not_there_is_the_base_code(monkeypatch: pytest.MonkeyPatch) -> None:
    assert MolycowError.exit_code == 1
    assert run_argv(monkeypatch, "--book", "/nowhere/at/all.sqlite3", "book", "counts") == 1


def test_a_value_the_pharmacy_cannot_read_is_a_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = CliRunner()
    bookfile = a_book(runner, tmp_path)
    assert ValidationError.exit_code == 2
    code = run_argv(
        monkeypatch,
        "--book",
        str(bookfile),
        "generator",
        "receipt",
        "COR-1",
        "--supplier",
        "Corren Isotopes",
        "--at",
        "not a moment",
        "--surface",
        "38",
        "--metre",
        "1.4",
        "--wipe",
        "140",
        "--by",
        "K. Ruzicka",
    )
    assert code == 2


def test_a_record_that_is_not_there_is_a_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = CliRunner()
    bookfile = a_book(runner, tmp_path)
    assert NotFoundError.exit_code == 3
    assert (
        run_argv(
            monkeypatch,
            "--book",
            str(bookfile),
            "customer",
            "close",
            "CU-0404",
            "--on",
            "2025-06-30",
        )
        == 3
    )


def test_a_record_that_is_already_there_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = CliRunner()
    bookfile = a_working_morning(runner, tmp_path)
    assert ConflictError.exit_code == 4
    code = run_argv(
        monkeypatch,
        "--book",
        str(bookfile),
        "badge",
        "record",
        "K. Ruzicka",
        "2025Q2",
        "--deep",
        "120",
        "--extremity",
        "1400",
        "--read",
        "2025-07-14",
    )
    assert code == 0
    assert code != ConflictError.exit_code


def test_a_rule_the_pharmacy_will_not_break_is_a_rule_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = CliRunner()
    bookfile = a_working_morning(runner, tmp_path)
    assert RuleError.exit_code == 5
    code = run_argv(
        monkeypatch,
        "--book",
        str(bookfile),
        "order",
        "cancel",
        "ORD-250407-01",
    )
    assert code == 5


def test_a_dose_that_cannot_be_released_is_a_release_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = CliRunner()
    bookfile = a_working_morning(runner, tmp_path)
    assert ReleaseError.exit_code == 6
    code = run_argv(
        monkeypatch,
        "--book",
        str(bookfile),
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
    assert code == 4


def test_a_safety_limit_is_its_own_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()
    bookfile = a_working_morning(runner, tmp_path)
    assert SafetyError.exit_code == 7
    code = run_argv(
        monkeypatch,
        "--book",
        str(bookfile),
        "waste",
        "open",
        "--kind",
        "vials",
        "--at",
        "2025-04-08 06:00",
    )
    assert code == 0


def test_a_command_that_works_is_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()
    bookfile = a_working_morning(runner, tmp_path)
    assert run_argv(monkeypatch, "--book", str(bookfile), "book", "verify") == 0
    assert (
        run_argv(monkeypatch, "--book", str(bookfile), "report", "day", "--on", "2025-04-08") == 0
    )


def test_a_click_error_keeps_click_s_own_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = CliRunner()
    bookfile = a_book(runner, tmp_path)
    assert run_argv(monkeypatch, "--book", str(bookfile), "gossip") == 2
