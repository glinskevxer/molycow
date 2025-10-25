"""Commands for the customer register."""

from __future__ import annotations

import datetime as dt

import click

from molycow.cli.session import Session
from molycow.clock import parse_day
from molycow.model import AuthorizedUser, Customer, CustomerKind
from molycow.store.register import AuthorizedUserRepository, CustomerRepository


@click.group()
def customer() -> None:
    """The hospitals and clinics this pharmacy ships to."""


@customer.command("add")
@click.argument("name")
@click.option("--kind", type=click.Choice([one.value for one in CustomerKind]), required=True)
@click.option("--licence", required=True, help="their radioactive materials licence")
@click.option("--street", required=True)
@click.option("--town", required=True)
@click.option("--zone", "zone_name", required=True)
@click.option("--opened", "opened_on", default=None, help="the day they came on the books")
@click.pass_obj
def customer_add(
    session: Session,
    name: str,
    kind: str,
    licence: str,
    street: str,
    town: str,
    zone_name: str,
    opened_on: str | None,
) -> None:
    """Put a customer on the books."""
    with session.open() as book:
        repo = CustomerRepository(book)
        day = parse_day(opened_on) if opened_on else dt.datetime.now(tz=session.tz).date()
        number = repo.count() + 1
        added = repo.add(
            Customer(
                id=f"CU-{number:04d}",
                name=name,
                kind=CustomerKind(kind),
                licence=licence,
                street=street,
                town=town,
                zone=zone_name,
                opened_on=day,
            )
        )
        click.echo(f"{added.id} {added.name} {added.kind.value} {added.zone}")


@customer.command("list")
@click.option("--zone", "zone_name", default=None, help="only this delivery zone")
@click.option("--on", "on_day", default=None, help="only the ones open on this day")
@click.pass_obj
def customer_list(session: Session, zone_name: str | None, on_day: str | None) -> None:
    """List the customers."""
    with session.open() as book:
        day = parse_day(on_day) if on_day else None
        found = CustomerRepository(book).all(zone=zone_name, open_on=day)
        if not found:
            click.echo("no customers")
            return
        for one in found:
            shut = "" if one.closed_on is None else f" closed {one.closed_on}"
            click.echo(f"{one.id}  {one.name:34} {one.kind.value:9} {one.zone:7}{shut}")


@customer.command("close")
@click.argument("customer_id")
@click.option("--on", "on_day", required=True)
@click.pass_obj
def customer_close(session: Session, customer_id: str, on_day: str) -> None:
    """Take a customer off the books without losing their records."""
    with session.open() as book:
        closed = CustomerRepository(book).close(customer_id, parse_day(on_day))
        click.echo(f"{closed.id} closed {closed.closed_on}")


@click.group()
def physician() -> None:
    """The authorized users named on a customer's licence."""


@physician.command("add")
@click.argument("customer_id")
@click.argument("name")
@click.option("--licence", required=True)
@click.option("--nuclide", "nuclides", multiple=True, required=True, help="repeat per nuclide")
@click.option("--added", "added_on", default=None)
@click.pass_obj
def physician_add(
    session: Session,
    customer_id: str,
    name: str,
    licence: str,
    nuclides: tuple[str, ...],
    added_on: str | None,
) -> None:
    """Name a physician on a customer's licence."""
    with session.open() as book:
        customers = CustomerRepository(book)
        customers.get(customer_id)
        users = AuthorizedUserRepository(book)
        existing = sum(len(users.for_customer(one.id)) for one in customers.all())
        day = parse_day(added_on) if added_on else dt.datetime.now(tz=session.tz).date()
        added = users.add(
            AuthorizedUser(
                id=f"AU-{existing + 1:04d}",
                customer_id=customer_id,
                name=name,
                licence=licence,
                added_on=day,
                nuclides=frozenset(nuclides),
            )
        )
        click.echo(f"{added.id} {added.name} at {added.customer_id}")


@physician.command("list")
@click.argument("customer_id")
@click.option("--on", "on_day", default=None, help="only the ones current that day")
@click.pass_obj
def physician_list(session: Session, customer_id: str, on_day: str | None) -> None:
    """List the physicians named at a customer."""
    with session.open() as book:
        day = parse_day(on_day) if on_day else None
        found = AuthorizedUserRepository(book).for_customer(customer_id, on=day)
        if not found:
            click.echo("nobody is named there")
            return
        for one in found:
            symbols = ", ".join(sorted(one.nuclides)) or "nothing"
            ended = "" if one.ended_on is None else f" ended {one.ended_on}"
            click.echo(f"{one.id}  {one.name:24} {symbols}{ended}")


@physician.command("end")
@click.argument("user_id")
@click.option("--on", "on_day", required=True)
@click.pass_obj
def physician_end(session: Session, user_id: str, on_day: str) -> None:
    """Take a physician off a licence."""
    with session.open() as book:
        ended = AuthorizedUserRepository(book).end(user_id, parse_day(on_day))
        click.echo(f"{ended.id} ended {ended.ended_on}")
