"""Commands for the badge file."""

from __future__ import annotations

from decimal import Decimal

import click

from molycow.cli.session import Session
from molycow.clock import parse_day
from molycow.service.dosimetry import DosimetryService


@click.group()
def badge() -> None:
    """The film badges and what they read."""


@badge.command("record")
@click.argument("person")
@click.argument("period")
@click.option("--deep", required=True, help="the whole body reading in mrem")
@click.option("--extremity", required=True, help="the finger reading in mrem")
@click.option("--read", "read_on", required=True, help="the day the service read it")
@click.pass_obj
def badge_record(
    session: Session, person: str, period: str, deep: str, extremity: str, read_on: str
) -> None:
    """Write one badge reading down."""
    with session.open() as book:
        reading = DosimetryService(book, session.tz).record(
            person, period, Decimal(deep), Decimal(extremity), parse_day(read_on)
        )
        click.echo(reading.line())


@badge.command("quarter")
@click.argument("period")
@click.pass_obj
def badge_quarter(session: Session, period: str) -> None:
    """Everybody's badge for one quarter, and anybody whose is missing."""
    with session.open() as book:
        service = DosimetryService(book, session.tz)
        for one in service.quarter(period):
            click.echo(one.line())
        missing = service.missing(period)
        if missing:
            click.echo("no reading yet for: " + ", ".join(missing))
        elif not service.quarter(period):
            click.echo("no badges have come back for that quarter")


@badge.command("year")
@click.argument("year", type=int)
@click.option("--person", default=None, help="one person rather than the watch list")
@click.pass_obj
def badge_year(session: Session, year: int, person: str | None) -> None:
    """The year so far, or the people worth a word about it."""
    with session.open() as book:
        service = DosimetryService(book, session.tz)
        if person is not None:
            click.echo(service.year_to_date(person, year).line())
            return
        watched = service.watch_list(year)
        if not watched:
            click.echo("nobody is near their limit")
            return
        for one in watched:
            click.echo(one.line())
