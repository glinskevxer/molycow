"""Commands for the order desk."""

from __future__ import annotations

import click

from molycow.cli.options import at_option, on_option_maybe
from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment, stamp
from molycow.formulary import codes
from molycow.model.order import Priority
from molycow.service.orders import OrderService
from molycow.store.orders import OrderRepository
from molycow.units import Activity


@click.group()
def order() -> None:
    """What the hospitals have asked for."""


@order.command("take")
@click.argument("customer_id")
@click.argument("user_id")
@click.option("--code", type=click.Choice(codes()), required=True)
@click.option("--procedure", required=True)
@click.option("--ref", "patient_ref", required=True, help="the department's own reference")
@click.option("--activity", required=True, help="what it must read at the calibration time")
@click.option("--calibration", required=True, help="when the department will inject it")
@click.option("--at", "ordered_at", required=True, help="when the order came in")
@click.option("--stat", is_flag=True, help="work it before anything routine")
@click.pass_obj
def order_take(
    session: Session,
    customer_id: str,
    user_id: str,
    code: str,
    procedure: str,
    patient_ref: str,
    activity: str,
    calibration: str,
    ordered_at: str,
    stat: bool,
) -> None:
    """Take an order, if the licence and the physician allow it."""
    with session.open() as book:
        taken = OrderService(book, session.tz).take(
            customer_id=customer_id,
            user_id=user_id,
            code=code,
            procedure=procedure,
            patient_ref=patient_ref,
            activity=Activity.parse(activity),
            calibration_at=parse_moment(calibration, session.tz),
            ordered_at=parse_moment(ordered_at, session.tz),
            priority=Priority.STAT if stat else Priority.ROUTINE,
        )
        click.echo(
            f"{taken.id} {taken.customer_id} {taken.code} "
            f"{taken.activity.format('mci', 1)} at {stamp(taken.calibration_at, session.tz)}"
        )


@order.command("check")
@click.argument("customer_id")
@click.argument("user_id")
@click.option("--code", type=click.Choice(codes()), required=True)
@click.option("--activity", required=True)
@click.option("--calibration", required=True)
@click.pass_obj
def order_check(
    session: Session,
    customer_id: str,
    user_id: str,
    code: str,
    activity: str,
    calibration: str,
) -> None:
    """Say whether an order would be taken, without writing it down."""
    with session.open() as book:
        refused = OrderService(book, session.tz).refusal_for(
            customer_id,
            user_id,
            code,
            Activity.parse(activity),
            parse_moment(calibration, session.tz),
        )
        if refused is None:
            click.echo("that order would be taken")
            return
        click.echo(f"refused [{refused.rule}] {refused.reason}")


@order.command("list")
@on_option_maybe("the orders calibrated that day")
@click.option("--customer", "customer_id", default=None)
@click.option("--open", "open_only", is_flag=True, help="only the ones still to fill")
@click.pass_obj
def order_list(
    session: Session, on_day: str | None, customer_id: str | None, open_only: bool
) -> None:
    """List the orders."""
    with session.open() as book:
        repo = OrderRepository(book)
        if customer_id is not None:
            found = repo.for_customer(customer_id)
        elif on_day is not None:
            found = repo.due_on(parse_day(on_day), session.tz)
        else:
            found = repo.all()
        if open_only:
            found = [one for one in found if one.is_open()]
        if on_day is not None and customer_id is not None:
            day = parse_day(on_day)
            found = [
                one for one in found if one.calibration_at.astimezone(session.tz).date() == day
            ]
        if not found:
            click.echo("no orders")
            return
        for one in found:
            click.echo(
                f"{one.id}  {one.customer_id}  {one.code:7} {one.activity.format('mci', 1):>10}  "
                f"{stamp(one.calibration_at, session.tz)}  {one.patient_ref:12} {one.state.value}"
            )


@order.command("worklist")
@at_option()
@click.option("--hours", type=int, default=4, show_default=True)
@click.pass_obj
def order_worklist(session: Session, moment: str, hours: int) -> None:
    """The open orders calibrated inside the next few hours."""
    with session.open() as book:
        found = OrderService(book, session.tz).worklist(parse_moment(moment, session.tz), hours)
        if not found:
            click.echo("nothing due")
            return
        for one in found:
            mark = "STAT " if one.is_stat else "     "
            click.echo(
                f"{mark}{stamp(one.calibration_at, session.tz)}  {one.id}  {one.customer_id}  "
                f"{one.code:7} {one.activity.format('mci', 1)}  {one.procedure}"
            )


@order.command("late")
@at_option()
@click.pass_obj
def order_late(session: Session, moment: str) -> None:
    """Orders whose calibration time has gone by with nothing drawn."""
    with session.open() as book:
        found = OrderService(book, session.tz).late(parse_moment(moment, session.tz))
        if not found:
            click.echo("nothing is late")
            return
        for one in found:
            click.echo(
                f"{one.id}  {one.customer_id}  wanted {stamp(one.calibration_at, session.tz)}"
            )


@order.command("cancel")
@click.argument("order_id")
@click.pass_obj
def order_cancel(session: Session, order_id: str) -> None:
    """Take an order back off the list."""
    with session.open() as book:
        cancelled = OrderService(book, session.tz).cancel(order_id)
        click.echo(f"{cancelled.id} cancelled")
