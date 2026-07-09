"""Commands that read the audit trail."""

from __future__ import annotations

import click

from molycow.cli.options import on_option
from molycow.cli.session import Session
from molycow.clock import parse_day
from molycow.store.audit import AuditRepository


@click.group()
def audit() -> None:
    """Who did what, and when."""


@audit.command("day")
@on_option()
@click.option("--actor", default=None, help="only what one person did")
@click.pass_obj
def audit_day(session: Session, on_day: str, actor: str | None) -> None:
    """Everything done on a day."""
    with session.open() as book:
        found = AuditRepository(book).on_day(parse_day(on_day), session.tz)
        if actor is not None:
            found = [one for one in found if one.actor == actor]
        if not found:
            click.echo("nothing was done")
            return
        for entry in found:
            click.echo(entry.line(session.tz))


@audit.command("record")
@click.argument("subject")
@click.pass_obj
def audit_record(session: Session, subject: str) -> None:
    """Everything done to one record."""
    with session.open() as book:
        found = AuditRepository(book).for_subject(subject)
        if not found:
            click.echo("nothing has been done to that record")
            return
        for entry in found:
            click.echo(entry.line(session.tz))


@audit.command("person")
@click.argument("actor")
@click.pass_obj
def audit_person(session: Session, actor: str) -> None:
    """Everything one person did."""
    with session.open() as book:
        found = AuditRepository(book).by_actor(actor)
        if not found:
            click.echo("that name has done nothing in this book")
            return
        for entry in found:
            click.echo(entry.line(session.tz))
        click.echo(f"{len(found)} entries")
