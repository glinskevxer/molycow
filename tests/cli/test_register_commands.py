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


def add_a_customer(runner: CliRunner, bookfile: Path, name: str = "Saint Brannon") -> Result:
    return call(
        runner,
        bookfile,
        "customer",
        "add",
        name,
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
    )


def test_a_customer_is_added_and_numbered(runner: CliRunner, bookfile: Path) -> None:
    result = add_a_customer(runner, bookfile)
    assert result.exit_code == 0
    assert result.output.startswith("CU-0001 Saint Brannon hospital north")


def test_customers_are_numbered_in_turn(runner: CliRunner, bookfile: Path) -> None:
    add_a_customer(runner, bookfile)
    second = add_a_customer(runner, bookfile, "Halvern Clinic")
    assert second.output.startswith("CU-0002")


def test_a_bad_licence_number_is_refused(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "customer",
        "add",
        "Nowhere General",
        "--kind",
        "clinic",
        "--licence",
        "nonsense",
        "--street",
        "1 Road",
        "--town",
        "Ardmore",
        "--zone",
        "north",
    )
    assert result.exit_code != 0
    assert "licence number" in str(result.exception)


def test_a_kind_the_pharmacy_does_not_know_is_refused(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "customer",
        "add",
        "Nowhere General",
        "--kind",
        "veterinary",
        "--licence",
        "42-28931-01",
        "--street",
        "1 Road",
        "--town",
        "Ardmore",
        "--zone",
        "north",
    )
    assert result.exit_code != 0


def test_the_customer_list_reads_as_a_table(runner: CliRunner, bookfile: Path) -> None:
    add_a_customer(runner, bookfile)
    result = call(runner, bookfile, "customer", "list")
    assert "CU-0001" in result.output
    assert "north" in result.output


def test_an_empty_register_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert "no customers" in call(runner, bookfile, "customer", "list").output


def test_the_list_can_be_narrowed_by_zone_and_day(runner: CliRunner, bookfile: Path) -> None:
    add_a_customer(runner, bookfile)
    assert "CU-0001" in call(runner, bookfile, "customer", "list", "--zone", "north").output
    assert "no customers" in call(runner, bookfile, "customer", "list", "--zone", "river").output
    early = call(runner, bookfile, "customer", "list", "--on", "2024-12-31")
    assert "no customers" in early.output


def test_closing_a_customer_keeps_them_readable(runner: CliRunner, bookfile: Path) -> None:
    add_a_customer(runner, bookfile)
    closed = call(runner, bookfile, "customer", "close", "CU-0001", "--on", "2025-06-30")
    assert "closed 2025-06-30" in closed.output
    assert "closed 2025-06-30" in call(runner, bookfile, "customer", "list").output


def test_a_physician_is_named_on_a_licence(runner: CliRunner, bookfile: Path) -> None:
    add_a_customer(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "physician",
        "add",
        "CU-0001",
        "R. Okonkwo",
        "--licence",
        "42-28931-01",
        "--nuclide",
        "Tc-99m",
        "--nuclide",
        "I-131",
        "--added",
        "2025-01-06",
    )
    assert result.output.startswith("AU-0001 R. Okonkwo at CU-0001")
    listed = call(runner, bookfile, "physician", "list", "CU-0001")
    assert "i131" in listed.output
    assert "tc99m" in listed.output


def test_a_physician_at_a_customer_that_is_not_there_is_refused(
    runner: CliRunner, bookfile: Path
) -> None:
    result = call(
        runner,
        bookfile,
        "physician",
        "add",
        "CU-0404",
        "R. Okonkwo",
        "--licence",
        "42-28931-01",
        "--nuclide",
        "Tc-99m",
    )
    assert result.exit_code != 0
    assert "no such customer" in str(result.exception)


def test_a_physician_can_be_ended_and_drops_off_the_current_list(
    runner: CliRunner, bookfile: Path
) -> None:
    add_a_customer(runner, bookfile)
    call(
        runner,
        bookfile,
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
    )
    call(runner, bookfile, "physician", "end", "AU-0001", "--on", "2025-03-01")
    current = call(runner, bookfile, "physician", "list", "CU-0001", "--on", "2025-04-08")
    assert "nobody is named there" in current.output


def test_a_customer_with_nobody_named(runner: CliRunner, bookfile: Path) -> None:
    add_a_customer(runner, bookfile)
    assert "nobody is named" in call(runner, bookfile, "physician", "list", "CU-0001").output
