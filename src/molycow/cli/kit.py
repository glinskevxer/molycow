"""Commands for the kit shelf and the compounding bench."""

from __future__ import annotations

from decimal import Decimal

import click

from molycow.cli.session import Session
from molycow.clock import day_of, parse_day, parse_moment, stamp
from molycow.formulary import codes, formula, known
from molycow.model.kit import KitLot
from molycow.model.purity import Strip, System
from molycow.service.compound import CompoundService
from molycow.service.fridge import FridgeService
from molycow.service.purity import PurityService
from molycow.service.recall import RecallService
from molycow.store.kits import KitLotRepository
from molycow.units import Activity, Volume


@click.group()
def kit() -> None:
    """The cold kits on the shelf and the batches made from them."""


@kit.command("formulary")
def kit_formulary() -> None:
    """The monographs this pharmacy compounds to."""
    for one in known():
        heat = "boil" if one.boil else "cold"
        click.echo(
            f"{one.code:7} {one.name:24} {one.nuclide:7} "
            f"{one.min_activity.format('mci', 0)} to {one.max_activity.format('mci', 0)} "
            f"in {one.min_volume} to {one.max_volume}  "
            f"{one.shelf_hours:g}h  rcp {one.rcp_floor}%  {heat}"
        )


@kit.command("add")
@click.argument("code", type=click.Choice(codes()))
@click.argument("lot")
@click.option("--maker", required=True)
@click.option("--received", "received_on", required=True)
@click.option("--expires", "expires_on", required=True)
@click.option("--vials", type=int, required=True)
@click.pass_obj
def kit_add(
    session: Session,
    code: str,
    lot: str,
    maker: str,
    received_on: str,
    expires_on: str,
    vials: int,
) -> None:
    """Book a box of cold kits onto the shelf."""
    with session.open() as book:
        repo = KitLotRepository(book)
        added = repo.add(
            KitLot(
                id=repo.next_id(),
                code=code,
                maker=maker,
                lot=lot,
                received_on=parse_day(received_on),
                expires_on=parse_day(expires_on),
                vials=vials,
            )
        )
        click.echo(f"{added.id} {added.code} lot {added.lot} {added.vials} vials")


@kit.command("shelf")
@click.option("--code", default=None, help="only this kit")
@click.option("--on", "on_day", default=None, help="only the lots in date that day")
@click.pass_obj
def kit_shelf(session: Session, code: str | None, on_day: str | None) -> None:
    """What is on the kit shelf."""
    with session.open() as book:
        repo = KitLotRepository(book)
        day = parse_day(on_day) if on_day else None
        found = repo.for_code(code, in_date_on=day) if code else repo.all()
        if day is not None and code is None:
            found = [one for one in found if one.is_in_date(day)]
        if not found:
            click.echo("nothing on the shelf")
            return
        for one in found:
            click.echo(
                f"{one.id}  {one.code:7} lot {one.lot:8} {one.vials:3d} vials "
                f"expires {one.expires_on}"
            )


@kit.command("plan")
@click.argument("code", type=click.Choice(codes()))
@click.argument("elution_id")
@click.option("--at", "moment", required=True)
@click.option("--activity", required=True)
@click.option("--volume", default=None, help="what the vial is made up to")
@click.pass_obj
def kit_plan(
    session: Session,
    code: str,
    elution_id: str,
    moment: str,
    activity: str,
    volume: str | None,
) -> None:
    """Work out a prep without writing it down."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        planned = CompoundService(book, session.tz).plan(
            code,
            elution_id,
            when,
            Activity.parse(activity),
            Volume.parse(volume) if volume else None,
        )
        click.echo(
            f"{planned.formula.code} from {elution_id}: draw {planned.eluate_volume} "
            f"and make up to {planned.volume} with {planned.saline} saline, "
            f"kit {planned.kit_lot.id}"
        )


@kit.command("compound")
@click.argument("code", type=click.Choice(codes()))
@click.argument("elution_id")
@click.option("--at", "moment", required=True)
@click.option("--activity", required=True)
@click.option("--volume", default=None)
@click.option("--by", "made_by", required=True)
@click.pass_obj
def kit_compound(
    session: Session,
    code: str,
    elution_id: str,
    moment: str,
    activity: str,
    volume: str | None,
    made_by: str,
) -> None:
    """Make a batch up and write it in the book."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        batch = CompoundService(book, session.tz).compound(
            code,
            elution_id,
            when,
            Activity.parse(activity),
            made_by,
            Volume.parse(volume) if volume else None,
        )
        click.echo(
            f"{batch.id} {batch.code} {batch.activity.format('mci', 1)} in {batch.volume}, "
            f"expires {stamp(batch.expires_at, session.tz)}"
        )


@kit.command("strips")
@click.argument("batch_id")
@click.option("--at", "moment", required=True)
@click.option("--solvent", nargs=2, type=int, required=True, help="origin and front counts")
@click.option("--saline", nargs=2, type=int, required=True, help="origin and front counts")
@click.option("--background", type=int, default=0)
@click.option("--by", "tested_by", required=True)
@click.pass_obj
def kit_strips(
    session: Session,
    batch_id: str,
    moment: str,
    solvent: tuple[int, int],
    saline: tuple[int, int],
    background: int,
    tested_by: str,
) -> None:
    """Read the two chromatography strips onto a batch."""
    with session.open() as book:
        reading = PurityService(book).run(
            batch_id,
            parse_moment(moment, session.tz),
            Strip(System.SOLVENT, origin=solvent[0], front=solvent[1], background=background),
            Strip(System.SALINE, origin=saline[0], front=saline[1], background=background),
            tested_by,
        )
        click.echo(f"{batch_id} {reading.note()}")


@kit.command("bench")
@click.option("--at", "moment", required=True)
@click.option("--code", default=None)
@click.pass_obj
def kit_bench(session: Session, moment: str, code: str | None) -> None:
    """What is on the bench right now, and what is held."""
    with session.open() as book:
        when = parse_moment(moment, session.tz)
        service = CompoundService(book, session.tz)
        ready = service.ready(when, code)
        held = service.held(when)
        if not ready and not held:
            click.echo("nothing on the bench")
            return
        for batch in ready:
            click.echo(
                f"{batch.id}  {batch.code:7} {batch.concentration_at(when).format('mci', 1)}  "
                f"expires {stamp(batch.expires_at, session.tz)}  ready"
            )
        for batch, reason in held:
            if code is not None and batch.code != code:
                continue
            click.echo(f"{batch.id}  {batch.code:7} held: {reason}")


@kit.command("day")
@click.option("--on", "on_day", required=True)
@click.pass_obj
def kit_day(session: Session, on_day: str) -> None:
    """Everything compounded on a day."""
    with session.open() as book:
        from molycow.store.kits import BatchRepository

        day = parse_day(on_day)
        found = BatchRepository(book).on_day(day, session.tz)
        if not found:
            click.echo("nothing was compounded")
            return
        for batch in found:
            purity = "no strips" if batch.rcp is None else f"rcp {batch.rcp}%"
            click.echo(
                f"{batch.id}  {batch.code:7} {batch.activity.format('mci', 1)}  "
                f"{day_of(batch.made_at, session.tz)}  {purity}  "
                f"floor {formula(batch.code).rcp_floor}%"
            )


@kit.command("recall")
@click.argument("lot_id")
@click.option("--at", "moment", required=True)
@click.option("--why", "reason", required=True, help="what the maker found")
@click.option("--by", "recalled_by", required=True)
@click.pass_obj
def kit_recall(session: Session, lot_id: str, moment: str, reason: str, recalled_by: str) -> None:
    """Pull a lot and print everything it reached."""
    with session.open() as book:
        reach = RecallService(book, session.tz).recall(
            lot_id, parse_moment(moment, session.tz), reason, recalled_by
        )
        for line in reach.lines():
            click.echo(line)
        if reach.is_empty:
            click.echo("  nothing was made from it")
        for shipment_id in reach.shipments:
            click.echo(f"  box {shipment_id} went out")


@kit.command("recalled")
@click.pass_obj
def kit_recalled(session: Session) -> None:
    """The lots that have been pulled, and what came out of them."""
    with session.open() as book:
        service = RecallService(book, session.tz)
        lots = service.recalled_lots()
        if not lots:
            click.echo("nothing has been recalled")
            return
        for lot in lots:
            assert lot.recalled_at is not None
            click.echo(
                f"{lot.id}  {lot.code:7} lot {lot.lot:8} pulled "
                f"{stamp(lot.recalled_at, session.tz)}  {lot.recall_reason}"
            )
        for batch in service.batches_from_recalled():
            click.echo(f"  batch {batch.id} came out of a pulled lot")


@kit.command("fridge")
@click.option("--at", "moment", required=True)
@click.option("--celsius", required=True, help="what the thermometer read")
@click.option("--by", "read_by", required=True)
@click.pass_obj
def kit_fridge(session: Session, moment: str, celsius: str, read_by: str) -> None:
    """Write a fridge reading down."""
    with session.open() as book:
        reading = FridgeService(book, session.tz).record(
            parse_moment(moment, session.tz), Decimal(celsius), read_by
        )
        click.echo(reading.line())


@kit.command("fridge-log")
@click.option("--on", "on_day", default=None)
@click.pass_obj
def kit_fridge_log(session: Session, on_day: str | None) -> None:
    """The fridge readings, and anything still open against them."""
    with session.open() as book:
        service = FridgeService(book, session.tz)
        found = service.readings_on(parse_day(on_day)) if on_day else []
        if on_day is None:
            for one in service.open_excursions():
                click.echo(one.line())
            if service.is_clear():
                click.echo("nothing open against the fridge")
            return
        if not found:
            click.echo("nobody read the fridge")
            return
        for one in found:
            click.echo(one.line())


@kit.command("fridge-review")
@click.option("--reading", "read_at", required=True, help="the moment of the reading")
@click.option("--at", "moment", required=True)
@click.option("--by", "reviewed_by", required=True)
@click.pass_obj
def kit_fridge_review(session: Session, read_at: str, moment: str, reviewed_by: str) -> None:
    """Close an excursion by putting a name against it."""
    with session.open() as book:
        reviewed = FridgeService(book, session.tz).review(
            parse_moment(read_at, session.tz),
            parse_moment(moment, session.tz),
            reviewed_by,
        )
        click.echo(reviewed.line())
