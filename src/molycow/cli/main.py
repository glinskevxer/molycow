"""The entry point, the shared options and the book commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from molycow import __version__
from molycow.cli.audit import audit
from molycow.cli.dose import dose
from molycow.cli.dosimetry import badge
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
from molycow.formulary import known as known_kits
from molycow.nuclides import known as known_nuclides
from molycow.rules import about, rules, subjects
from molycow.store.migrations import apply, latest, pending, schema_version

EPILOG = """\
A morning, in the order it happens:

  molycow book init
  molycow customer add "Saint Brannon" --kind hospital --licence 42-28931-01 \\
      --street "1400 Weir Street" --town Ardmore --zone north
  molycow instrument check IC-0001 CS-9912 --at "2025-04-08 06:05" \\
      --read "175 uCi" --by "K. Ruzicka"
  molycow generator milk GEN-0001 --at "2025-04-08 06:30" \\
      --volume "10 mL" --activity "940 mCi"
  molycow generator test EL-250408-01 --at "2025-04-08 06:45" \\
      --moly "0.9 uCi" --aluminium 4 --by "K. Ruzicka"
  molycow kit compound MDP EL-250408-01 --at "2025-04-08 07:15" \\
      --activity "300 mCi" --by "K. Ruzicka"
  molycow dose draw ORD-250407-01 B-250408-01 --at "2025-04-08 07:40" \\
      --assay "25.65 mCi" --by "K. Ruzicka" --calibrator IC-0001
  molycow report day --on 2025-04-08

Times are local. Activities carry their unit: '25 mCi', '925 MBq', '300 uCi'.
'molycow book laws' lists every rule the pharmacy will refuse on.
"""


@click.group(epilog=EPILOG)
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
        counts = [(name, opened.row_count(name)) for name in opened.tables()]
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
run.add_command(audit)
run.add_command(badge)
run.add_command(physician)


@book.command("verify")
@click.pass_obj
def book_verify(session: Session) -> None:
    """Ask sqlite whether the file is sound and the keys still hold."""
    with session.open() as opened:
        problems = opened.integrity()
        for problem in problems:
            click.echo(problem)
        if problems:
            raise MolycowError(f"that book has {len(problems)} problems in it")
        click.echo(f"{session.path} is sound, {len(opened.tables())} tables")


@book.command("backup")
@click.argument("target", type=click.Path(dir_okay=False, path_type=Path))
@click.pass_obj
def book_backup(session: Session, target: Path) -> None:
    """Copy the book to another file while it is open."""
    with session.open() as opened:
        written = opened.backup(target)
        rows = sum(opened.row_count(name) for name in opened.tables())
    click.echo(f"{written} written, {rows} rows")


@book.command("laws")
@click.option("--about", "subject", default=None, help="only the rules about one thing")
@click.pass_obj
def book_laws(session: Session, subject: str | None) -> None:
    """The rules this package refuses on, and what each one says."""
    if subject is not None and subject not in subjects():
        raise click.BadParameter(f"try one of: {', '.join(subjects())}")
    found = about(subject) if subject else rules()
    for rule in found:
        click.echo(rule.line())
    click.echo(f"{len(found)} rules, {session.path}")


@run.command("about")
@click.pass_obj
def about_command(session: Session) -> None:
    """What this build is, and what the book it was pointed at holds.

    The first thing anybody asks when a command does something surprising is
    which build and which book, so this answers both in five lines rather than
    in a support call.
    """
    click.echo(f"molycow  {__version__}")
    click.echo(f"schema   {latest()} expected")
    click.echo(f"rules    {len(rules())} in {len(subjects())} groups")
    click.echo(f"nuclides {len(known_nuclides())} handled, {len(known_kits())} kits compounded")
    click.echo(f"zone     {session.zone_name}")
    if not session.path.exists():
        click.echo(f"book     {session.path}, not there yet")
        return
    with session.open(migrated=False) as opened:
        rows = sum(opened.row_count(name) for name in opened.tables())
        click.echo(
            f"book     {session.path}, schema {schema_version(opened)}, "
            f"{len(opened.tables())} tables, {rows} rows"
        )


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
