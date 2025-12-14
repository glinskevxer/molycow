"""Commands for the survey round."""

from __future__ import annotations

from decimal import Decimal

import click

from molycow.cli.session import Session
from molycow.clock import parse_day, parse_moment, stamp
from molycow.model.survey import WIPE_LIMIT_DPM, Area, DoseRate, Wipe
from molycow.service.survey import SurveyService
from molycow.store.surveys import SurveyRepository


@click.group()
def survey() -> None:
    """Walking the building with a meter and a swab."""


@survey.command("walk")
@click.option("--at", "moment", required=True)
@click.option("--by", "surveyed_by", required=True)
@click.option(
    "--read",
    "readings",
    nargs=2,
    multiple=True,
    help="an area and a reading in mrem/h, repeated",
)
@click.option(
    "--wipe",
    "wipes",
    nargs=4,
    multiple=True,
    help="area, spot, counts and background, repeated",
)
@click.option("--efficiency", default="0.35", show_default=True, help="the counter efficiency")
@click.pass_obj
def survey_walk(
    session: Session,
    moment: str,
    surveyed_by: str,
    readings: tuple[tuple[str, str], ...],
    wipes: tuple[tuple[str, str, str, str], ...],
    efficiency: str,
) -> None:
    """Write down a round of the building."""
    with session.open() as book:
        walked = SurveyService(book, session.tz).walk(
            parse_moment(moment, session.tz),
            surveyed_by,
            [(Area(area), DoseRate.of(reading)) for area, reading in readings],
            [
                Wipe(
                    area=Area(area),
                    spot=spot,
                    counts=int(counts),
                    background=int(background),
                    efficiency=Decimal(efficiency),
                )
                for area, spot, counts, background in wipes
            ],
        )
        failure = walked.failure()
        click.echo(f"{walked.id} {len(walked.readings)} readings {len(walked.wipes)} wipes")
        if failure is not None:
            click.echo(f"FAILED: {failure}")


@survey.command("day")
@click.option("--on", "on_day", required=True)
@click.pass_obj
def survey_day(session: Session, on_day: str) -> None:
    """What was surveyed on a day and what was missed."""
    with session.open() as book:
        day = parse_day(on_day)
        service = SurveyService(book, session.tz)
        walked = SurveyRepository(book).on_day(day, session.tz)
        if not walked:
            click.echo("nobody walked the building")
        for one in walked:
            click.echo(
                f"{one.id}  {stamp(one.at, session.tz)}  {one.surveyed_by}  "
                f"{'clean' if one.passes() else one.failure()}"
            )
        missed = service.areas_missed(day)
        if missed:
            click.echo("not surveyed: " + ", ".join(area.value for area in missed))
        worst = service.worst_area_on(day)
        if worst is not None:
            click.echo(f"hottest {worst[0].value} {worst[1]}")


@survey.command("open")
@click.option(
    "--limit",
    default=str(WIPE_LIMIT_DPM),
    show_default=True,
    help="the removable contamination limit in dpm",
)
@click.pass_obj
def survey_open(session: Session, limit: str) -> None:
    """Dirty spots with no clean wipe of the same spot after them."""
    with session.open() as book:
        found = SurveyService(book, session.tz).open_failures(Decimal(limit))
        if not found:
            click.echo("nothing is open")
            return
        for one in found:
            click.echo(one.note())


@survey.command("areas")
def survey_areas() -> None:
    """The areas that get surveyed, and the limit on each."""
    for area in Area:
        held = "restricted" if area.is_restricted else "public"
        click.echo(f"{area.value:16} {held:10} {area.dose_rate_limit} mrem/h")
