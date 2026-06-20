"""A week of work, driven through the services in the order a pharmacy does it.

The unit tests hold each rule on its own. This one asks the question the rules
are for: after five mornings of milking, compounding, drawing, shipping and
surveying, does the book still add up.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from tests.support import (
    CLEAN_SALINE,
    CLEAN_SOLVENT,
    a_calibrator,
    a_generator,
    a_kit_lot,
    a_register,
)

from molycow.clock import parse_moment, zone
from molycow.model.survey import Area, DoseRate, Wipe
from molycow.model.waste import ContainerKind
from molycow.report.daysheet import day_sheet
from molycow.report.period import month, period_sheet
from molycow.service.breakthrough import BreakthroughService
from molycow.service.compound import CompoundService
from molycow.service.dispense import DispenseService
from molycow.service.elution import ElutionService
from molycow.service.inventory import InventoryService
from molycow.service.orders import OrderService
from molycow.service.purity import PurityService
from molycow.service.shipping import ShippingService
from molycow.service.survey import SurveyService
from molycow.service.waste import WasteService
from molycow.store import Book
from molycow.store.audit import AuditRepository
from molycow.store.doses import DoseRepository
from molycow.units import Activity, Volume

TZ = zone()
DAYS = (
    dt.date(2025, 4, 7),
    dt.date(2025, 4, 8),
    dt.date(2025, 4, 9),
    dt.date(2025, 4, 10),
    dt.date(2025, 4, 11),
)

READINGS = [
    (Area.HOT_LAB, DoseRate.of("1.2")),
    (Area.DISPENSING, DoseRate.of("0.8")),
    (Area.PACKAGING, DoseRate.of("0.3")),
    (Area.WASTE, DoseRate.of("2.1")),
]


def at_on(day: dt.date, clock: str) -> dt.datetime:
    """A local moment on one of the week's days."""
    return parse_moment(f"{day.isoformat()} {clock}", TZ)


def a_week(book: Book) -> dict[str, int]:
    """Run five mornings and give back what the week produced."""
    a_register(book)
    a_generator(book, "GEN-0027", received_on=DAYS[0], expires_on=dt.date(2025, 4, 21))
    a_kit_lot(book)
    a_calibrator(book, checked=False)
    orders = OrderService(book, TZ)
    elutions = ElutionService(book, TZ)
    tests = BreakthroughService(book)
    compounding = CompoundService(book, TZ)
    purity = PurityService(book)
    dispensing = DispenseService(book, TZ)
    shipping = ShippingService(book, TZ)
    surveys = SurveyService(book, TZ)
    waste = WasteService(book, TZ)
    counts = {"doses": 0, "boxes": 0}
    from molycow.model.qc import CheckKind
    from molycow.service.qc import QcService

    qc = QcService(book, TZ)
    for day in DAYS:
        source_reading = a_source_reading(book, day)
        qc.run(
            "IC-0003",
            CheckKind.CONSTANCY,
            "CS-9912",
            at_on(day, "06:05"),
            source_reading,
            "K. Ruzicka",
        )
        order = orders.take(
            customer_id="CU-0001",
            user_id="AU-0004",
            code="MDP",
            procedure="whole body bone",
            patient_ref=f"A-{day.strftime('%m%d')}",
            activity=Activity.of(22, "mci"),
            calibration_at=at_on(day, "09:00"),
            ordered_at=at_on(day, "05:30"),
        )
        expected = elutions.expected_from("GEN-0027", at_on(day, "06:30"))
        milking = elutions.milk(
            "GEN-0027", at_on(day, "06:30"), Volume.of(10), expected.scaled("0.92")
        )
        tests.test(
            milking.elution.id,
            at_on(day, "06:45"),
            Activity.of("0.9", "uci"),
            Decimal(4),
            "K. Ruzicka",
        )
        batch = compounding.compound(
            "MDP",
            milking.elution.id,
            at_on(day, "07:15"),
            Activity.of(250, "mci"),
            "K. Ruzicka",
            volume=Volume.of(8),
        )
        purity.run(batch.id, at_on(day, "07:35"), CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
        planned = dispensing.plan(order.id, batch.id, at_on(day, "07:40"))
        dose = dispensing.draw(
            order.id,
            batch.id,
            at_on(day, "07:40"),
            planned.needed,
            "K. Ruzicka",
            "IC-0003",
        )
        counts["doses"] += 1
        box = shipping.pack(
            "CU-0001",
            [dose.id],
            at_on(day, "08:20"),
            "K. Ruzicka",
            Decimal(12),
            Decimal("0.35"),
        )
        shipping.deliver(box.id, at_on(day, "09:05"), "Reception")
        counts["boxes"] += 1
        drum = waste.container_for(ContainerKind.VIALS, at_on(day, "06:00"))
        waste.discard(
            drum.id,
            "Tc-99m",
            Activity.of(40, "mci"),
            at_on(day, "16:00"),
            milking.elution.id,
        )
        surveys.walk(
            at_on(day, "17:40"),
            "K. Ruzicka",
            READINGS,
            [Wipe(Area.HOT_LAB, "draw station", 300, 120, Decimal("0.35"))],
        )
    return counts


def a_source_reading(book: Book, day: dt.date) -> Activity:
    from molycow.store.instruments import CheckSourceRepository

    return CheckSourceRepository(book).get("CS-9912").activity_on(day)


def test_five_mornings_leave_five_doses_and_five_boxes(book: Book) -> None:
    counts = a_week(book)
    assert counts == {"doses": 5, "boxes": 5}
    assert len(DoseRepository(book).all()) == 5


def test_every_day_of_the_week_has_a_full_day_sheet(book: Book) -> None:
    a_week(book)
    for day in DAYS:
        sheet = day_sheet(book, day, TZ)
        assert len(sheet.section("elutions").rows) == 1
        assert len(sheet.section("doses").rows) == 1
        assert len(sheet.section("shipments").rows) == 1
        assert sheet.section("survey").rows[0].startswith("hottest reading")


def test_the_month_adds_the_week_up(book: Book) -> None:
    a_week(book)
    rows = period_sheet(book, month(2025, 4), TZ).section("work").rows
    assert "5 elutions" in rows[1]
    assert "5 batches" in rows[2]
    assert "5 doses" in rows[3]


def test_nothing_delivered_is_still_counted_as_on_the_premises(book: Book) -> None:
    a_week(book)
    inventory = InventoryService(book, TZ)
    holdings = inventory.holdings(at_on(DAYS[-1], "18:00"))
    assert holdings["Tc-99m"].place("doses").is_zero()
    assert holdings["Tc-99m"].place("waste") > Activity.zero()
    assert inventory.over_limit(at_on(DAYS[-1], "18:00")) == []


def test_the_column_is_worth_less_by_friday(book: Book) -> None:
    a_week(book)
    inventory = InventoryService(book, TZ)
    monday = inventory.holding_of("Mo-99", at_on(DAYS[0], "06:00"))
    friday = inventory.holding_of("Mo-99", at_on(DAYS[-1], "06:00"))
    assert friday < monday
    assert friday > monday.scaled("0.2")


def test_the_trail_carries_every_step_of_every_day(book: Book) -> None:
    a_week(book)
    trail = AuditRepository(book).all()
    actions = [one.action for one in trail]
    assert actions.count("milked") == 5
    assert actions.count("drew") == 5
    assert actions.count("delivered") == 5
    assert actions.count("surveyed") == 5


def test_the_days_work_belongs_to_the_day_it_happened(book: Book) -> None:
    a_week(book)
    for day in DAYS:
        entries = AuditRepository(book).on_day(day, TZ)
        assert {one.action for one in entries} >= {"milked", "drew", "packed"}
