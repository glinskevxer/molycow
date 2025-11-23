"""Commands for the dock."""

from __future__ import annotations

from decimal import Decimal

import click

from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment, stamp
from molycow.service.shipping import ShippingService
from molycow.store.shipments import ShipmentRepository


@click.group()
def ship() -> None:
    """Packing boxes and getting them signed for."""


@ship.command("ready")
@click.argument("customer_id")
@click.option("--at", "moment", required=True)
@click.pass_obj
def ship_ready(session: Session, customer_id: str, moment: str) -> None:
    """Doses drawn for a customer that are not in a box yet."""
    with session.open() as book:
        found = ShippingService(book, session.tz).ready_for(
            customer_id, parse_moment(moment, session.tz)
        )
        if not found:
            click.echo("nothing waiting")
            return
        for dose_id in found:
            click.echo(dose_id)


@ship.command("pack")
@click.argument("customer_id")
@click.argument("dose_ids", nargs=-1, required=True)
@click.option("--at", "moment", required=True)
@click.option("--by", "packed_by", required=True)
@click.option("--surface", required=True, help="the reading on the box, in mrem/h")
@click.option("--metre", required=True, help="the reading a metre away, in mrem/h")
@click.pass_obj
def ship_pack(
    session: Session,
    customer_id: str,
    dose_ids: tuple[str, ...],
    moment: str,
    packed_by: str,
    surface: str,
    metre: str,
) -> None:
    """Close a box and read it."""
    with session.open() as book:
        box = ShippingService(book, session.tz).pack(
            customer_id,
            list(dose_ids),
            parse_moment(moment, session.tz),
            packed_by,
            Decimal(surface),
            Decimal(metre),
        )
        click.echo(box.manifest_line())
        click.echo(f"a2 fraction {box.a2_fraction:.4f}")


@ship.command("deliver")
@click.argument("shipment_id")
@click.option("--at", "moment", required=True)
@click.option("--to", "received_by", required=True)
@click.pass_obj
def ship_deliver(session: Session, shipment_id: str, moment: str, received_by: str) -> None:
    """Sign a box over at the hospital."""
    with session.open() as book:
        signed = ShippingService(book, session.tz).deliver(
            shipment_id, parse_moment(moment, session.tz), received_by
        )
        assert signed.delivered_at is not None
        click.echo(
            f"{signed.id} signed by {signed.received_by} "
            f"at {stamp(signed.delivered_at, session.tz)}"
        )


@ship.command("manifest")
@click.option("--on", "on_day", required=True)
@click.pass_obj
def ship_manifest(session: Session, on_day: str) -> None:
    """The day's boxes, with the index the van is carrying."""
    with session.open() as book:
        manifest = ShippingService(book, session.tz).manifest(parse_day(on_day))
        if not manifest.shipments:
            click.echo("nothing left the dock")
            return
        for line in manifest.lines():
            click.echo(line)
        click.echo(f"{manifest.dose_count} doses, vehicle index {manifest.vehicle_index}")


@ship.command("outstanding")
@click.pass_obj
def ship_outstanding(session: Session) -> None:
    """Boxes that have not been signed for."""
    with session.open() as book:
        found = ShippingService(book, session.tz).outstanding()
        if not found:
            click.echo("everything has been signed for")
            return
        for box in found:
            click.echo(
                f"{box.id}  {box.customer_id}  packed {stamp(box.packed_at, session.tz)}  "
                f"{box.dose_count} doses"
            )


@ship.command("show")
@click.argument("shipment_id")
@click.pass_obj
def ship_show(session: Session, shipment_id: str) -> None:
    """What is in one box."""
    with session.open() as book:
        box = ShipmentRepository(book).get(shipment_id)
        click.echo(box.manifest_line())
        for dose_id in box.dose_ids:
            click.echo(f"  {dose_id}")
        if box.delivered_at is not None:
            click.echo(f"  signed by {box.received_by} {stamp(box.delivered_at, session.tz)}")
