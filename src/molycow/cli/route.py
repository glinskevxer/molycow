"""Commands for the courier runs."""

from __future__ import annotations

import click

from molycow.cli.options import at_option, on_option
from molycow.cli.session import Session
from molycow.clock import parse_clock, parse_day, parse_moment, stamp
from molycow.model.route import Route
from molycow.service.route import RouteService
from molycow.store.routes import RouteRepository


@click.group()
def route() -> None:
    """The standing runs and the day they are driven."""


@route.command("add")
@click.argument("name")
@click.option("--zone", "zone_name", required=True)
@click.option("--leaves", required=True, help="the departure time, as '0630'")
@click.option("--stop", "stops", multiple=True, required=True, help="repeat per customer")
@click.pass_obj
def route_add(
    session: Session, name: str, zone_name: str, leaves: str, stops: tuple[str, ...]
) -> None:
    """Set up a standing run."""
    with session.open() as book:
        repo = RouteRepository(book)
        added = repo.add(
            Route(
                id=repo.next_id(),
                name=name,
                zone=zone_name,
                stops=tuple(stops),
                leaves_at=parse_clock(leaves),
            )
        )
        click.echo(
            f"{added.id} {added.name} {added.zone} leaves {added.leaves_at:%H:%M} "
            f"{added.stop_count} stops"
        )


@route.command("list")
@click.option("--zone", "zone_name", default=None)
@click.pass_obj
def route_list(session: Session, zone_name: str | None) -> None:
    """The standing runs."""
    with session.open() as book:
        repo = RouteRepository(book)
        found = repo.for_zone(zone_name) if zone_name else repo.all()
        if not found:
            click.echo("no routes")
            return
        for one in found:
            click.echo(
                f"{one.id}  {one.name:22} {one.zone:7} {one.leaves_at:%H:%M}  "
                f"{', '.join(one.stops)}"
            )


@route.command("open")
@click.argument("route_id")
@on_option()
@click.option("--driver", required=True)
@click.pass_obj
def route_open(session: Session, route_id: str, on_day: str, driver: str) -> None:
    """Open a day of a route."""
    with session.open() as book:
        run = RouteService(book, session.tz).open_run(route_id, parse_day(on_day), driver)
        click.echo(f"{run.route_id} {run.day} driver {run.driver}")


@route.command("waiting")
@click.argument("route_id")
@click.pass_obj
def route_waiting(session: Session, route_id: str) -> None:
    """Boxes for this run's stops that are not on a van yet."""
    with session.open() as book:
        found = RouteService(book, session.tz).waiting_for(route_id)
        if not found:
            click.echo("nothing waiting")
            return
        for box in found:
            click.echo(f"{box.id}  {box.customer_id}  TI {box.transport_index}")


@route.command("load")
@click.argument("route_id")
@click.argument("shipment_id")
@on_option()
@click.pass_obj
def route_load(session: Session, route_id: str, shipment_id: str, on_day: str) -> None:
    """Put a box on a run."""
    with session.open() as book:
        load = RouteService(book, session.tz).load(route_id, parse_day(on_day), shipment_id)
        click.echo(
            f"{route_id} carrying {len(load.shipments)} boxes, index {load.index}, "
            f"stops {', '.join(load.stops_with_boxes)}"
        )


@route.command("depart")
@click.argument("route_id")
@on_option()
@at_option()
@click.pass_obj
def route_depart(session: Session, route_id: str, on_day: str, moment: str) -> None:
    """Send the van out."""
    with session.open() as book:
        run = RouteService(book, session.tz).depart(
            route_id, parse_day(on_day), parse_moment(moment, session.tz)
        )
        assert run.left_at is not None
        click.echo(f"{run.route_id} left at {stamp(run.left_at, session.tz)}")


@route.command("deliver")
@click.argument("route_id")
@click.argument("shipment_id")
@on_option()
@at_option()
@click.option("--to", "received_by", required=True)
@click.pass_obj
def route_deliver(
    session: Session,
    route_id: str,
    shipment_id: str,
    on_day: str,
    moment: str,
    received_by: str,
) -> None:
    """Sign a box over at a stop on the run."""
    with session.open() as book:
        signed = RouteService(book, session.tz).deliver(
            route_id,
            parse_day(on_day),
            shipment_id,
            parse_moment(moment, session.tz),
            received_by,
        )
        click.echo(f"{signed.id} signed by {signed.received_by}")


@route.command("back")
@click.argument("route_id")
@on_option()
@at_option()
@click.pass_obj
def route_back(session: Session, route_id: str, on_day: str, moment: str) -> None:
    """Book the van back in, and say what came back with it."""
    with session.open() as book:
        service = RouteService(book, session.tz)
        day = parse_day(on_day)
        run = service.arrive_back(route_id, day, parse_moment(moment, session.tz))
        load = service.load_of(route_id, day)
        assert run.returned_at is not None
        click.echo(f"{run.route_id} back at {stamp(run.returned_at, session.tz)}")
        for box in load.undelivered():
            click.echo(f"  {box.id} came back undelivered")
