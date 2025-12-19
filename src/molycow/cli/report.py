"""Commands that print reports."""

from __future__ import annotations

import click

from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment
from molycow.report.daysheet import day_sheet
from molycow.service.inventory import InventoryService
from molycow.store.licence import LicenceRepository


@click.group()
def report() -> None:
    """The sheets the pharmacy prints."""


@report.command("day")
@click.option("--on", "on_day", required=True)
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


@report.command("holdings")
@click.option("--at", "moment", required=True)
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
@click.option("--at", "moment", required=True)
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
