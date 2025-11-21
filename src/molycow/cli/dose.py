"""Commands for the dispensing bench."""

from __future__ import annotations

from decimal import Decimal

import click

from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment, stamp
from molycow.model.dose import TOLERANCE_PERCENT
from molycow.service.dispense import DispenseService
from molycow.store.doses import DoseRepository
from molycow.store.orders import OrderRepository
from molycow.units import Activity, Volume


@click.group()
def dose() -> None:
    """Drawing syringes against orders."""


@dose.command("plan")
@click.argument("order_id")
@click.argument("batch_id")
@click.option("--at", "moment", required=True)
@click.pass_obj
def dose_plan(session: Session, order_id: str, batch_id: str, moment: str) -> None:
    """Work out the draw without filling anything."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        planned = DispenseService(book, session.tz).plan(order_id, batch_id, when)
        click.echo(
            f"{order_id} from {batch_id}: draw {planned.volume} "
            f"reading {planned.needed.format('mci', 2)} now for "
            f"{planned.label_activity.format('mci', 1)} at "
            f"{stamp(planned.order.calibration_at, session.tz)}"
        )


@dose.command("batches")
@click.argument("order_id")
@click.option("--at", "moment", required=True)
@click.pass_obj
def dose_batches(session: Session, order_id: str, moment: str) -> None:
    """Which batches on the bench could fill an order."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        found = DispenseService(book, session.tz).batches_for(order_id, when)
        if not found:
            click.echo("nothing on the bench would fill it")
            return
        for batch in found:
            click.echo(
                f"{batch.id}  {batch.code:7} {batch.concentration_at(when).format('mci', 1)}  "
                f"expires {stamp(batch.expires_at, session.tz)}"
            )


@dose.command("draw")
@click.argument("order_id")
@click.argument("batch_id")
@click.option("--at", "moment", required=True)
@click.option("--assay", required=True, help="what the calibrator read on the syringe")
@click.option("--by", "drawn_by", required=True)
@click.option("--calibrator", "calibrator_id", required=True)
@click.option("--volume", default=None, help="what was actually drawn, if not the plan")
@click.option(
    "--tolerance",
    default=str(TOLERANCE_PERCENT),
    show_default=True,
    help="how far off the order the assay may be, as a percentage",
)
@click.pass_obj
def dose_draw(
    session: Session,
    order_id: str,
    batch_id: str,
    moment: str,
    assay: str,
    drawn_by: str,
    calibrator_id: str,
    volume: str | None,
    tolerance: str,
) -> None:
    """Fill a syringe, assay it and close the order."""
    with session.open() as book:
        drawn = DispenseService(book, session.tz).draw(
            order_id,
            batch_id,
            parse_moment(moment, session.tz),
            Activity.parse(assay),
            drawn_by,
            calibrator_id,
            Volume.parse(volume) if volume else None,
            Decimal(tolerance),
        )
        order = OrderRepository(book).get(order_id)
        click.echo(
            f"{drawn.id} {drawn.volume} reading {drawn.assayed.format('mci', 2)}, "
            f"{drawn.at_calibration.format('mci', 2)} at calibration "
            f"({drawn.variance_from(order.activity):+}%)"
        )
        click.echo(drawn.label(order.activity, session.tz))


@dose.command("label")
@click.argument("dose_id")
@click.pass_obj
def dose_label(session: Session, dose_id: str) -> None:
    """Reprint the line that goes on a syringe shield."""
    with session.open() as book:
        drawn = DoseRepository(book).get(dose_id)
        order = OrderRepository(book).get(drawn.order_id)
        click.echo(drawn.label(order.activity, session.tz))


@dose.command("list")
@click.option("--on", "on_day", required=True)
@click.pass_obj
def dose_list(session: Session, on_day: str) -> None:
    """The syringes drawn on a day."""
    with session.open() as book:
        found = DoseRepository(book).on_day(parse_day(on_day), session.tz)
        if not found:
            click.echo("nothing was drawn")
            return
        orders = OrderRepository(book)
        for drawn in found:
            order = orders.get(drawn.order_id)
            click.echo(
                f"{drawn.id}  {order.customer_id}  {drawn.code:7} {drawn.volume:>10}  "
                f"{stamp(drawn.drawn_at, session.tz)}  {order.patient_ref:12} "
                f"{drawn.variance_from(order.activity):+}%"
            )


@dose.command("batch")
@click.argument("batch_id")
@click.pass_obj
def dose_batch(session: Session, batch_id: str) -> None:
    """What has been drawn out of a batch, and what is left in it."""
    with session.open() as book:
        service = DispenseService(book, session.tz)
        for drawn in DoseRepository(book).for_batch(batch_id):
            click.echo(f"{drawn.id}  {drawn.volume}  {stamp(drawn.drawn_at, session.tz)}")
        click.echo(f"{service.remaining_in(batch_id)} left of {batch_id}")
