"""The two days a year the local clock is not a clock.

Everything in this package is stored in utc and worked in local time, and the
two are only the same thing on the other 363 days. These tests drive a real
morning across both changes, because the arithmetic that goes wrong here goes
wrong quietly: a dose that reads right and is an hour out.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from tests.support import (
    CLEAN_SALINE,
    CLEAN_SOLVENT,
    a_calibrator,
    a_kit_lot,
    a_register,
)

from molycow.clock import day_of, hours_between, parse_moment, zone
from molycow.errors import ValidationError
from molycow.model.generator import Generator
from molycow.report.daysheet import day_sheet
from molycow.service.breakthrough import BreakthroughService
from molycow.service.compound import CompoundService
from molycow.service.dispense import DispenseService
from molycow.service.elution import ElutionService
from molycow.service.orders import OrderService
from molycow.service.purity import PurityService
from molycow.store import Book
from molycow.store.generators import GeneratorRepository
from molycow.units import Activity, Volume

TZ = zone()

SPRING = dt.date(2025, 3, 9)
AUTUMN = dt.date(2025, 11, 2)


def at_on(day: dt.date, clock: str) -> dt.datetime:
    return parse_moment(f"{day.isoformat()} {clock}", TZ)


def a_bench(book: Book, day: dt.date) -> str:
    """A register, a column milked at six, and a kit on the shelf."""
    a_register(book)
    GeneratorRepository(book).add(
        Generator(
            id="GEN-0027",
            serial="M99-44182",
            maker="Corren Isotopes",
            calibrated_at=at_on(day - dt.timedelta(days=3), "12:00"),
            calibrated_activity=Activity.of(2, "Ci"),
            received_on=day - dt.timedelta(days=3),
            expires_on=day + dt.timedelta(days=11),
        )
    )
    a_kit_lot(
        book, received_on=day - dt.timedelta(days=30), expires_on=day + dt.timedelta(days=300)
    )
    a_calibrator(book, checked=False)
    milking = ElutionService(book, TZ).milk(
        "GEN-0027", at_on(day, "06:00"), Volume.of(10), Activity.of(900, "mCi")
    )
    BreakthroughService(book).test(
        milking.elution.id,
        at_on(day, "06:15"),
        Activity.of("0.9", "uci"),
        Decimal(4),
        "K. Ruzicka",
    )
    return milking.elution.id


def test_the_hour_the_clocks_skip_cannot_be_written_down() -> None:
    with pytest.raises(ValidationError, match="clocks moved"):
        at_on(SPRING, "02:30")


def test_three_hours_on_the_wall_is_two_real_hours_in_march(book: Book) -> None:
    a_bench(book, SPRING)
    early = at_on(SPRING, "01:30")
    late = at_on(SPRING, "04:30")
    assert hours_between(early, late) == Decimal(2)
    assert early.utcoffset() != late.utcoffset()


def test_a_dose_drawn_before_the_change_is_calibrated_after_it(book: Book) -> None:
    elution_id = a_bench(book, SPRING)
    order = OrderService(book, TZ).take(
        customer_id="CU-0001",
        user_id="AU-0004",
        code="MDP",
        procedure="whole body bone",
        patient_ref="A-0309",
        activity=Activity.of(22, "mci"),
        calibration_at=at_on(SPRING, "09:00"),
        ordered_at=at_on(SPRING, "05:30"),
    )
    compounding = CompoundService(book, TZ)
    batch = compounding.compound(
        "MDP", elution_id, at_on(SPRING, "06:30"), Activity.of(300, "mci"), "K. Ruzicka"
    )
    PurityService(book).run(
        batch.id, at_on(SPRING, "06:45"), CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka"
    )
    from molycow.model.qc import CheckKind
    from molycow.service.qc import QcService
    from molycow.store.instruments import CheckSourceRepository

    reading = CheckSourceRepository(book).get("CS-9912").activity_on(SPRING)
    QcService(book, TZ).run(
        "IC-0003", CheckKind.CONSTANCY, "CS-9912", at_on(SPRING, "05:05"), reading, "K. Ruzicka"
    )
    dispensing = DispenseService(book, TZ)
    drawn_at = at_on(SPRING, "01:30")
    planned = dispensing.plan(order.id, batch.id, at_on(SPRING, "06:50"))
    dose = dispensing.draw(
        order.id, batch.id, at_on(SPRING, "06:50"), planned.needed, "K. Ruzicka", "IC-0003"
    )
    assert drawn_at < dose.drawn_at
    assert dose.at_calibration.format("mci", 1) == "22.0 mCi"
    assert dose.label(order.activity, TZ).endswith("at 0900")


def test_the_shortest_day_of_the_year_is_still_one_day(book: Book) -> None:
    a_bench(book, SPRING)
    sheet = day_sheet(book, SPRING, TZ)
    assert len(sheet.section("elutions").rows) == 1
    assert day_of(at_on(SPRING, "23:30"), TZ) == SPRING


def test_the_hour_the_clocks_repeat_takes_the_earlier_one(book: Book) -> None:
    a_bench(book, AUTUMN)
    first = at_on(AUTUMN, "01:30")
    assert first.utcoffset() == dt.timedelta(hours=-5)
    assert day_of(first, TZ) == AUTUMN


def test_an_eluate_expires_twelve_real_hours_after_the_autumn_change(book: Book) -> None:
    elution_id = a_bench(book, AUTUMN)
    from molycow.store.generators import ElutionRepository

    elution = ElutionRepository(book).get(elution_id)
    assert hours_between(elution.drawn_at, elution.expires_at) == Decimal(12)
    assert elution.drawn_at.astimezone(TZ).utcoffset() == dt.timedelta(hours=-6)
    assert elution.expires_at.astimezone(TZ).hour == 18


def test_a_batch_made_before_the_autumn_change_expires_in_real_hours(book: Book) -> None:
    elution_id = a_bench(book, AUTUMN)
    batch = CompoundService(book, TZ).compound(
        "MDP", elution_id, at_on(AUTUMN, "06:30"), Activity.of(300, "mci"), "K. Ruzicka"
    )
    assert hours_between(batch.made_at, batch.expires_at) == Decimal(6)


def test_the_days_work_lands_on_the_local_day_both_times(book: Book) -> None:
    for day in (SPRING, AUTUMN):
        with Book.in_memory() as fresh:
            from molycow.store.migrations import apply

            apply(fresh)
            a_bench(fresh, day)
            assert len(day_sheet(fresh, day, TZ).section("elutions").rows) == 1
            assert day_sheet(fresh, day + dt.timedelta(days=1), TZ).section("elutions").is_empty
