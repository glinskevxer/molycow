"""Commands for the instruments and their checks."""

from __future__ import annotations

import click

from molycow.cli.options import at_option, on_option, on_option_maybe
from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment, stamp
from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
from molycow.model.qc import CheckKind, LinearityPoint
from molycow.report.instruments import instrument_sheet
from molycow.service.qc import QcService
from molycow.store.instruments import CheckSourceRepository, InstrumentRepository, QcRepository
from molycow.units import Activity


@click.group()
def instrument() -> None:
    """The calibrators, meters and the sources they are checked with."""


@instrument.command("add")
@click.argument("serial")
@click.option("--kind", type=click.Choice([one.value for one in InstrumentKind]), required=True)
@click.option("--maker", required=True)
@click.option("--model", "model_name", required=True)
@click.option("--installed", "installed_on", required=True)
@click.option("--calibrated", "calibrated_on", required=True)
@click.pass_obj
def instrument_add(
    session: Session,
    serial: str,
    kind: str,
    maker: str,
    model_name: str,
    installed_on: str,
    calibrated_on: str,
) -> None:
    """Put an instrument on the books."""
    with session.open() as book:
        repo = InstrumentRepository(book)
        added = repo.add(
            Instrument(
                id=repo.next_id(),
                kind=InstrumentKind(kind),
                maker=maker,
                model=model_name,
                serial=serial,
                installed_on=parse_day(installed_on),
                calibrated_on=parse_day(calibrated_on),
            )
        )
        click.echo(f"{added.id} {added} due {added.calibration_due}")


@instrument.command("list")
@on_option_maybe("only the ones usable that day")
@click.pass_obj
def instrument_list(session: Session, on_day: str | None) -> None:
    """The instruments."""
    with session.open() as book:
        found = InstrumentRepository(book).all()
        if on_day is not None:
            day = parse_day(on_day)
            found = [one for one in found if one.is_usable_on(day)]
        if not found:
            click.echo("no instruments")
            return
        for one in found:
            click.echo(
                f"{one.id}  {one.kind.value:16} {one}  calibration due {one.calibration_due}"
            )


@instrument.command("source")
@click.argument("serial")
@click.option("--nuclide", "symbol", required=True)
@click.option("--activity", required=True, help="the certified activity")
@click.option("--certified", "certified_on", required=True)
@click.pass_obj
def instrument_source(
    session: Session, serial: str, symbol: str, activity: str, certified_on: str
) -> None:
    """Put a sealed check source on the shelf."""
    with session.open() as book:
        added = CheckSourceRepository(book).add(
            CheckSource(
                serial=serial,
                symbol=symbol,
                certified_activity=Activity.parse(activity),
                certified_on=parse_day(certified_on),
            )
        )
        click.echo(
            f"{added.serial} {added.symbol} {added.certified_activity.format('uci', 1)} "
            f"certified {added.certified_on}"
        )


@instrument.command("sources")
@on_option()
@click.pass_obj
def instrument_sources(session: Session, on_day: str) -> None:
    """The sources in use on a day, with what they read now."""
    with session.open() as book:
        day = parse_day(on_day)
        found = CheckSourceRepository(book).in_use_on(day)
        if not found:
            click.echo("no sources")
            return
        for one in found:
            click.echo(
                f"{one.serial}  {one.symbol:7} certified "
                f"{one.certified_activity.format('uci', 1)} reads "
                f"{one.activity_on(day).format('uci', 1)}"
            )


@instrument.command("check")
@click.argument("instrument_id")
@click.argument("source_serial")
@click.option(
    "--kind",
    type=click.Choice([one.value for one in CheckKind]),
    default=CheckKind.CONSTANCY.value,
    show_default=True,
)
@at_option()
@click.option("--read", "measured", required=True, help="what the instrument read")
@click.option("--by", "checked_by", required=True)
@click.pass_obj
def instrument_check(
    session: Session,
    instrument_id: str,
    source_serial: str,
    kind: str,
    moment: str,
    measured: str,
    checked_by: str,
) -> None:
    """Run a check against a sealed source."""
    with session.open() as book:
        result = QcService(book, session.tz).run(
            instrument_id,
            CheckKind(kind),
            source_serial,
            parse_moment(moment, session.tz),
            Activity.parse(measured),
            checked_by,
        )
        click.echo(result.note())
        click.echo(f"expected {result.check.expected.format('uci', 1)}")


@instrument.command("linearity")
@click.argument("instrument_id")
@click.option("--nuclide", "symbol", default="Tc-99m", show_default=True)
@click.option(
    "--read",
    "readings",
    nargs=2,
    multiple=True,
    required=True,
    help="a moment and an activity, repeated",
)
@click.option("--by", "checked_by", required=True)
@click.pass_obj
def instrument_linearity(
    session: Session,
    instrument_id: str,
    symbol: str,
    readings: tuple[tuple[str, str], ...],
    checked_by: str,
) -> None:
    """Read a source down over days and say whether the curve holds."""
    with session.open() as book:
        points = [
            LinearityPoint(parse_moment(moment, session.tz), Activity.parse(activity))
            for moment, activity in readings
        ]
        run = QcService(book, session.tz).linearity(instrument_id, symbol, points, checked_by)
        verdict = "passed" if run.passes() else "FAILED"
        click.echo(f"{instrument_id} linearity {verdict}, worst {run.worst}%")
        for point, off in zip(run.points, run.deviations(), strict=True):
            click.echo(
                f"  {stamp(point.at, session.tz)}  {point.measured.format('mci', 2)}  {off:+}%"
            )


@instrument.command("due")
@click.argument("instrument_id")
@on_option()
@click.pass_obj
def instrument_due(session: Session, instrument_id: str, on_day: str) -> None:
    """Which checks have run past their interval."""
    with session.open() as book:
        overdue = QcService(book, session.tz).overdue(instrument_id, parse_day(on_day))
        if not overdue:
            click.echo("nothing is overdue")
            return
        for kind in overdue:
            click.echo(f"{kind.value} overdue")


@instrument.command("history")
@click.argument("instrument_id")
@click.option("--kind", type=click.Choice([one.value for one in CheckKind]), default=None)
@click.pass_obj
def instrument_history(session: Session, instrument_id: str, kind: str | None) -> None:
    """Every check run against an instrument."""
    with session.open() as book:
        found = QcRepository(book).for_instrument(instrument_id, CheckKind(kind) if kind else None)
        if not found:
            click.echo("no checks")
            return
        for one in found:
            click.echo(f"{stamp(one.at, session.tz)}  {one.source_serial}  {one.note()}")


@instrument.command("board")
@on_option("the day to read the board for")
@click.pass_obj
def instrument_board(session: Session, on_day: str) -> None:
    """What is due, what is overdue, and what has failed."""
    with session.open() as book:
        click.echo(instrument_sheet(book, parse_day(on_day), session.tz).text())
