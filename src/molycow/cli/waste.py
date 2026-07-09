"""Commands for the waste store."""

from __future__ import annotations

from decimal import Decimal

import click

from molycow.cli.options import at_option
from molycow.cli.session import Session
from molycow.clock import parse_moment, stamp
from molycow.model.waste import ContainerKind
from molycow.service.waste import BACKGROUND_MREM, WasteService
from molycow.store.waste import ContainerRepository
from molycow.units import Activity


@click.group()
def waste() -> None:
    """Decay in storage."""


@waste.command("open")
@click.option("--kind", type=click.Choice([one.value for one in ContainerKind]), required=True)
@at_option()
@click.pass_obj
def waste_open(session: Session, kind: str, moment: str) -> None:
    """Open a container."""
    with session.open() as book:
        container = WasteService(book, session.tz).open_container(
            ContainerKind(kind), parse_moment(moment, session.tz)
        )
        click.echo(f"{container.id} {container.kind.value} opened")


@waste.command("discard")
@click.argument("container_id")
@click.option("--nuclide", "symbol", required=True)
@click.option("--activity", required=True)
@at_option()
@click.option("--from", "source", required=True, help="what it came out of")
@click.pass_obj
def waste_discard(
    session: Session, container_id: str, symbol: str, activity: str, moment: str, source: str
) -> None:
    """Drop something into an open container."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        container = WasteService(book, session.tz).discard(
            container_id, symbol, Activity.parse(activity), when, source
        )
        assert container.clear_at is not None
        click.echo(
            f"{container_id} holds {len(container.items)} items, "
            f"clear {stamp(container.clear_at, session.tz)}"
        )


@waste.command("dose")
@click.argument("container_id")
@click.argument("dose_id")
@at_option()
@click.pass_obj
def waste_dose(session: Session, container_id: str, dose_id: str, moment: str) -> None:
    """Put an unused syringe away at what it reads now."""
    with session.open() as book:
        container = WasteService(book, session.tz).discard_dose(
            container_id, dose_id, parse_moment(moment, session.tz)
        )
        click.echo(f"{container_id} took {dose_id}, {len(container.items)} items")


@waste.command("close")
@click.argument("container_id")
@at_option()
@click.pass_obj
def waste_close(session: Session, container_id: str, moment: str) -> None:
    """Close a container and start its hold."""
    with session.open() as book:
        closed = WasteService(book, session.tz).close(
            container_id, parse_moment(moment, session.tz)
        )
        assert closed.clear_at is not None
        click.echo(f"{closed.id} closed, clear {stamp(closed.clear_at, session.tz)}")


@waste.command("store")
@at_option()
@click.pass_obj
def waste_store(session: Session, moment: str) -> None:
    """What is in the store, and why each drum is still there."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        service = WasteService(book, session.tz)
        held = service.held(when)
        ready = service.ready(when)
        if not held and not ready:
            click.echo("the store is empty")
            return
        for one in held:
            click.echo(f"{one.container.id}  {one.container.kind.value:7} {one.reason}")
        for container in ready:
            click.echo(
                f"{container.id}  {container.kind.value:7} ready to survey out, "
                f"reads {container.activity_at(when).format('uci', 1)}"
            )
        click.echo(f"store holding {service.activity_in_store(when).format('mci', 2)}")


@waste.command("dispose")
@click.argument("container_id")
@at_option()
@click.option("--by", "disposed_by", required=True)
@click.option("--survey", "survey_mrem", required=True, help="the reading with the label off")
@click.pass_obj
def waste_dispose(
    session: Session, container_id: str, moment: str, disposed_by: str, survey_mrem: str
) -> None:
    """Take the label off, if the hold and the survey both allow it."""
    with session.open() as book:
        gone = WasteService(book, session.tz).dispose(
            container_id,
            parse_moment(moment, session.tz),
            disposed_by,
            Decimal(survey_mrem),
        )
        assert gone.disposed_at is not None
        click.echo(
            f"{gone.id} disposed {stamp(gone.disposed_at, session.tz)} by {disposed_by}, "
            f"surveyed {survey_mrem} against {BACKGROUND_MREM} mrem/h"
        )


@waste.command("show")
@click.argument("container_id")
@click.pass_obj
def waste_show(session: Session, container_id: str) -> None:
    """What went into one container."""
    with session.open() as book:
        container = ContainerRepository(book).get(container_id)
        for item in container.items:
            click.echo(
                f"{stamp(item.added_at, session.tz)}  {item.symbol:7} "
                f"{item.activity.format('mci', 2):>12}  from {item.source}  "
                f"clear {stamp(item.clear_at, session.tz)}"
            )
        if not container.items:
            click.echo("nothing has gone in it")
