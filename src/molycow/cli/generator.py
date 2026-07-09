"""Commands for the generator bench."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import click

from molycow.cli.options import at_option, on_option, on_option_maybe
from molycow.cli.session import Session
from molycow.clock import day_of, parse_day, parse_moment, stamp
from molycow.model.generator import Generator
from molycow.service.breakthrough import BreakthroughService
from molycow.service.elution import ElutionService
from molycow.service.inventory import InventoryService
from molycow.service.receipt import ReceiptService
from molycow.store.generators import ElutionRepository, GeneratorRepository
from molycow.units import Activity, Volume


@click.group()
def generator() -> None:
    """The molybdenum columns on the bench."""


@generator.command("receive")
@click.argument("serial")
@click.option("--maker", required=True)
@click.option("--activity", required=True, help="the calibrated molybdenum, as '2 Ci'")
@click.option("--calibrated", required=True, help="when it was calibrated, local time")
@click.option("--received", "received_on", required=True)
@click.option("--expires", "expires_on", required=True)
@click.option("--package", "package_reference", default=None, help="the carrier's reference")
@click.pass_obj
def generator_receive(
    session: Session,
    serial: str,
    maker: str,
    activity: str,
    calibrated: str,
    received_on: str,
    expires_on: str,
    package_reference: str | None,
) -> None:
    """Book a column in, if the licence has room for it."""
    with session.open() as book:
        moment = parse_moment(calibrated, session.tz)
        strength = Activity.parse(activity)
        InventoryService(book, session.tz).require_room_for("Mo-99", strength, moment)
        receipts = ReceiptService(book, session.tz)
        if package_reference is not None:
            receipts.require_clean(package_reference)
        repo = GeneratorRepository(book)
        column = repo.add(
            Generator(
                id=repo.next_id(),
                serial=serial,
                maker=maker,
                calibrated_at=moment,
                calibrated_activity=strength,
                received_on=parse_day(received_on),
                expires_on=parse_day(expires_on),
            )
        )
        if package_reference is not None:
            receipts.link(column.id, package_reference)
        click.echo(f"{column.id} {column.serial} {column.calibrated_activity.format('ci', 2)}")


@generator.command("list")
@on_option_maybe("only the ones in date that day")
@click.pass_obj
def generator_list(session: Session, on_day: str | None) -> None:
    """List the columns."""
    with session.open() as book:
        repo = GeneratorRepository(book)
        found = repo.in_date_on(parse_day(on_day)) if on_day else repo.all()
        if not found:
            click.echo("no columns on the bench")
            return
        for one in found:
            retired = "" if one.retired_on is None else f" retired {one.retired_on}"
            click.echo(
                f"{one.id}  {one.serial:12} expires {one.expires_on} "
                f"calibrated {one.calibrated_activity.format('ci', 2)}{retired}"
            )


@generator.command("retire")
@click.argument("generator_id")
@on_option()
@click.pass_obj
def generator_retire(session: Session, generator_id: str, on_day: str) -> None:
    """Take a column off the bench to go back to the maker."""
    with session.open() as book:
        retired = GeneratorRepository(book).retire(generator_id, parse_day(on_day))
        click.echo(f"{retired.id} retired {retired.retired_on}")


@generator.command("expect")
@click.argument("generator_id")
@at_option()
@click.pass_obj
def generator_expect(session: Session, generator_id: str, moment: str) -> None:
    """Say what a column should give up if it were milked now."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        expected = ElutionService(book, session.tz).expected_from(generator_id, when)
        click.echo(
            f"{generator_id} should give {expected.format('mci', 1)} at {stamp(when, session.tz)}"
        )


@generator.command("milk")
@click.argument("generator_id")
@at_option()
@click.option("--volume", required=True, help="what came off, as '10 mL'")
@click.option("--activity", required=True, help="what the calibrator read")
@click.option("--force", is_flag=True, help="accept a poor yield anyway")
@click.option("--by", "milked_by", default="the hot lab", show_default=True)
@click.pass_obj
def generator_milk(
    session: Session,
    generator_id: str,
    moment: str,
    volume: str,
    activity: str,
    force: bool,
    milked_by: str,
) -> None:
    """Milk a column and write the elution down."""
    with session.open() as book:
        milking = ElutionService(book, session.tz).milk(
            generator_id,
            parse_moment(moment, session.tz),
            Volume.parse(volume),
            Activity.parse(activity),
            force=force,
            milked_by=milked_by,
        )
        click.echo(
            f"{milking.elution.id} {milking.elution.activity.format('mci', 1)} "
            f"in {milking.elution.volume} at {milking.percent}% of expected"
        )
        if milking.note is not None:
            click.echo(milking.note)


@generator.command("test")
@click.argument("elution_id")
@at_option()
@click.option("--moly", required=True, help="the molybdenum found, as '0.9 uCi'")
@click.option("--aluminium", "aluminium_ppm", required=True, type=str)
@click.option("--by", "tested_by", required=True)
@click.pass_obj
def generator_test(
    session: Session,
    elution_id: str,
    moment: str,
    moly: str,
    aluminium_ppm: str,
    tested_by: str,
) -> None:
    """Run the breakthrough test on an eluate."""
    with session.open() as book:
        service = BreakthroughService(book)
        reading = service.test(
            elution_id,
            parse_moment(moment, session.tz),
            Activity.parse(moly),
            Decimal(aluminium_ppm),
            tested_by,
        )
        failed = reading.failure()
        if failed is not None:
            click.echo(f"{elution_id} FAILED: {failed}")
            return
        release = service.release(elution_id)
        click.echo(
            f"{elution_id} passed at {reading.ratio:.4f} uCi/mCi, "
            f"good until {stamp(release.good_until, session.tz)} "
            f"({release.ends_because})"
        )


@generator.command("eluates")
@at_option()
@click.pass_obj
def generator_eluates(session: Session, moment: str) -> None:
    """The eluate vials that may still be drawn from."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        service = ElutionService(book, session.tz)
        vials = service.in_date_eluates(when)
        if not vials:
            click.echo("nothing in date")
            return
        release = BreakthroughService(book)
        for vial in vials:
            state = "released" if release.may_draw(vial.id, when) else "held"
            click.echo(
                f"{vial.id}  {vial.concentration_at(when).format('mci', 1)}  "
                f"{vial.activity_at(when).format('mci', 1)} left  {state}"
            )


@generator.command("log")
@on_option_maybe()
@click.pass_obj
def generator_log(session: Session, on_day: str | None) -> None:
    """The elution log, for a day or for the whole book."""
    with session.open() as book:
        repo = ElutionRepository(book)
        day: dt.date | None = parse_day(on_day) if on_day else None
        found = repo.on_day(day, session.tz) if day else repo.all()
        if not found:
            click.echo("no elutions")
            return
        for one in found:
            click.echo(
                f"{one.id}  {one.generator_id}  {stamp(one.drawn_at, session.tz)}  "
                f"{one.activity.format('mci', 1)}  "
                f"{one.efficiency * Decimal(100):.1f}% of expected  "
                f"{day_of(one.drawn_at, session.tz)}"
            )


@generator.command("receipt")
@click.argument("reference")
@click.option("--supplier", required=True)
@at_option()
@click.option("--surface", required=True, help="the reading on the box, in mrem/h")
@click.option("--metre", required=True, help="the reading a metre away, in mrem/h")
@click.option("--wipe", "wipe_dpm", required=True, help="the wipe of the outside, in dpm")
@click.option("--by", "received_by", required=True)
@click.pass_obj
def generator_receipt(
    session: Session,
    reference: str,
    supplier: str,
    moment: str,
    surface: str,
    metre: str,
    wipe_dpm: str,
    received_by: str,
) -> None:
    """Book a package in with the readings taken on it."""
    with session.open() as book:
        receipt = ReceiptService(book, session.tz).receive(
            reference,
            supplier,
            parse_moment(moment, session.tz),
            Decimal(surface),
            Decimal(metre),
            Decimal(wipe_dpm),
            received_by,
        )
        click.echo(receipt.line())


@generator.command("receipts")
@on_option_maybe()
@click.pass_obj
def generator_receipts(session: Session, on_day: str | None) -> None:
    """The packages booked in, or the ones that failed."""
    with session.open() as book:
        service = ReceiptService(book, session.tz)
        found = service.on_day(parse_day(on_day)) if on_day else service.failures()
        if not found:
            click.echo("nothing to report" if on_day is None else "no packages that day")
            return
        for one in found:
            click.echo(one.line())
