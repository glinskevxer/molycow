"""The entry point, the shared options and the book commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from molycow import __version__
from molycow.cli.dose import dose
from molycow.cli.generator import generator
from molycow.cli.instrument import instrument
from molycow.cli.kit import kit
from molycow.cli.order import order
from molycow.cli.register import customer, physician
from molycow.cli.report import report
from molycow.cli.route import route
from molycow.cli.session import Session
from molycow.cli.ship import ship
from molycow.cli.survey import survey
from molycow.cli.waste import waste
from molycow.clock import DEFAULT_ZONE
from molycow.errors import MolycowError
from molycow.store.migrations import apply, latest, pending, schema_version


@click.group()
@click.option(
    "--book",
    "book_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default="molycow.sqlite3",
    show_default=True,
    envvar="MOLYCOW_BOOK",
    help="the sqlite file this pharmacy keeps its records in",
)
@click.option(
    "--zone",
    "zone_name",
    default=DEFAULT_ZONE,
    show_default=True,
    help="the time zone the pharmacy works to",
)
@click.version_option(__version__, prog_name="molycow")
@click.pass_context
def run(ctx: click.Context, book_path: Path, zone_name: str) -> None:
    """Hot lab records for a nuclear pharmacy."""
    ctx.obj = Session(book_path, zone_name)


@run.group()
def book() -> None:
    """Make, migrate and check the book itself."""


@book.command("init")
@click.pass_obj
def book_init(session: Session) -> None:
    """Create the book and bring it up to the current schema."""
    existed = session.path.exists()
    with session.create() as opened:
        ran = apply(opened)
    if existed and not ran:
        click.echo(f"{session.path} was already at schema {latest()}")
        return
    click.echo(f"{session.path} is at schema {latest()}, {len(ran)} steps applied")


@book.command("migrate")
@click.option("--upto", type=int, default=None, help="stop at this schema version")
@click.pass_obj
def book_migrate(session: Session, upto: int | None) -> None:
    """Run the migrations this book has not run yet."""
    with session.open(migrated=False) as opened:
        waiting = pending(opened)
        if not waiting:
            click.echo(f"nothing to do, the book is at schema {schema_version(opened)}")
            return
        ran = apply(opened, upto)
        for step in ran:
            click.echo(f"{step.number:3d}  {step.name}")
        click.echo(f"the book is at schema {schema_version(opened)}")


@book.command("check")
@click.pass_obj
def book_check(session: Session) -> None:
    """Say what schema the book is at and whether it matches this build."""
    with session.open(migrated=False) as opened:
        at = schema_version(opened)
        click.echo(f"book     {session.path}")
        click.echo(f"schema   {at} of {latest()}")
        click.echo(f"zone     {session.zone_name}")
        if at != latest():
            raise MolycowError("that book is not at the schema this build expects")


@book.command("counts")
@click.pass_obj
def book_counts(session: Session) -> None:
    """Count the rows in every table, largest first."""
    with session.open() as opened:
        tables = [
            str(row["name"])
            for row in opened.all(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
            if not str(row["name"]).startswith("sqlite_")
        ]
        counts = [(name, int(opened.value(f"SELECT count(*) FROM {name}") or 0)) for name in tables]
        for name, count in sorted(counts, key=lambda pair: (-pair[1], pair[0])):
            click.echo(f"{count:6d}  {name}")


run.add_command(customer)
run.add_command(generator)
run.add_command(kit)
run.add_command(order)
run.add_command(dose)
run.add_command(ship)
run.add_command(route)
run.add_command(instrument)
run.add_command(survey)
run.add_command(waste)
run.add_command(report)
run.add_command(physician)


def main() -> int:
    """Run the cli, turning our own errors into exit codes rather than stacks."""
    try:
        run.main(standalone_mode=False)
    except MolycowError as error:
        click.echo(f"molycow: {error}", err=True)
        return error.exit_code
    except click.ClickException as error:
        error.show()
        return error.exit_code
    except click.Abort:
        click.echo("aborted", err=True)
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
