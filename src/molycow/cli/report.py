"""Commands that print reports."""

from __future__ import annotations

from pathlib import Path

import click

from molycow.cli.options import at_option, on_option
from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment
from molycow.report.daysheet import day_sheet
from molycow.report.export import export_day
from molycow.report.period import Period, month, period_sheet
from molycow.report.statement import statement
from molycow.service.inventory import InventoryService
from molycow.store.licence import LicenceRepository


@click.group()
def report() -> None:
    """The sheets the pharmacy prints."""


@report.command("day")
@on_option()
@click.option("--section", default=None, help="print one section only")
@click.pass_obj
def report_day(session: Session, on_day: str, section: str | None) -> None:
    """The hot lab day sheet."""
    with session.open() as book:
        sheet = day_sheet(book, parse_day(on_day), session.tz)
        if section is None:
            click.echo(sheet.text())
            return
        if not sheet.has(section):
            raise click.BadParameter(
                f"no section called {section!r}, try one of: "
                + ", ".join(one.title for one in sheet.sections)
            )
        for line in sheet.section(section).lines():
            click.echo(line)


@report.command("month")
@click.argument("year", type=int)
@click.argument("number", type=int)
@click.pass_obj
def report_month(session: Session, year: int, number: int) -> None:
    """The period report for a calendar month."""
    with session.open() as book:
        click.echo(period_sheet(book, month(year, number), session.tz).text())


@report.command("period")
@click.option("--from", "first", required=True)
@click.option("--to", "last", required=True)
@click.pass_obj
def report_period(session: Session, first: str, last: str) -> None:
    """The period report between two days."""
    with session.open() as book:
        over = Period(parse_day(first), parse_day(last))
        if over.last < over.first:
            raise click.BadParameter("that period ends before it starts")
        click.echo(period_sheet(book, over, session.tz).text())


@report.command("holdings")
@at_option()
@click.option("--place", is_flag=True, help="break each nuclide down by where it is")
@click.pass_obj
def report_holdings(session: Session, moment: str, place: bool) -> None:
    """What is on the premises at a moment, against the licence."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        checks = InventoryService(book, session.tz).check(when)
        if not checks:
            click.echo("nothing on the premises")
            return
        for check in checks:
            share = (
                "no limit on file" if check.share is None else f"{check.share * 100:.1f}% of limit"
            )
            flag = "  OVER" if check.over else ""
            total = check.holding.total.format("mci", 1)
            click.echo(f"{check.holding.symbol:7} {total:>14}  {share}{flag}")
            if place:
                for name, activity in sorted(check.holding.by_place.items()):
                    click.echo(f"    {name:12} {activity.format('mci', 1)}")


@report.command("licence")
@click.pass_obj
def report_licence(session: Session) -> None:
    """The possession limits the licence sets."""
    with session.open() as book:
        for limit in LicenceRepository(book).all():
            click.echo(f"{limit.format():20} {limit.note}")


@report.command("room")
@click.argument("symbol")
@at_option()
@click.pass_obj
def report_room(session: Session, symbol: str, moment: str) -> None:
    """How much more of a nuclide the licence would allow right now."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        service = InventoryService(book, session.tz)
        limit = LicenceRepository(book).get(symbol)
        holding = service.holding_of(limit.symbol, when)
        click.echo(
            f"{limit.symbol} holding {holding.format('mci', 1)} of "
            f"{limit.limit.format('ci', 1)}, room for "
            f"{limit.headroom(holding).format('mci', 1)}"
        )


@report.command("export")
@click.argument("folder", type=click.Path(file_okay=False, path_type=Path))
@on_option()
@click.pass_obj
def report_export(session: Session, folder: Path, on_day: str) -> None:
    """Write a day out as csv."""
    with session.open() as book:
        written = export_day(book, parse_day(on_day), folder, session.tz)
        for one in written:
            click.echo(one.line())
        click.echo(f"{sum(one.rows for one in written)} rows into {folder}")


@report.command("statement")
@click.argument("customer_id")
@click.option("--year", type=int, required=True)
@click.option("--month", "number", type=int, required=True)
@click.pass_obj
def report_statement(session: Session, customer_id: str, year: int, number: int) -> None:
    """One customer's month, as their own office asks for it."""
    with session.open() as book:
        click.echo(statement(book, customer_id, month(year, number), session.tz).text())
