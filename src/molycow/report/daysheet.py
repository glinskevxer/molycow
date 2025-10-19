"""The hot lab day sheet: everything that happened, in the order it happened.

This is the sheet that gets printed at the end of the day, signed, and put in
the folder. It reads from the repositories only, because a report that can
change something is a report nobody trusts.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import combine, stamp, zone
from molycow.report.sheet import Section, Sheet
from molycow.service.inventory import InventoryService
from molycow.service.survey import SurveyService
from molycow.service.waste import WasteService
from molycow.store.book import Book
from molycow.store.breakthrough import BreakthroughRepository
from molycow.store.doses import DoseRepository
from molycow.store.generators import ElutionRepository
from molycow.store.kits import BatchRepository
from molycow.store.orders import OrderRepository
from molycow.store.shipments import ShipmentRepository


def day_sheet(book: Book, day: dt.date, tz: ZoneInfo | None = None) -> Sheet:
    """Build the day sheet for a local day."""
    where = tz or zone()
    close = combine(day, dt.time(23, 59), where)
    return Sheet(
        title=f"hot lab day sheet {day.isoformat()}",
        sections=(
            _elutions(book, day, where),
            _batches(book, day, where),
            _doses(book, day, where),
            _shipments(book, day, where),
            _survey(book, day, where),
            _waste(book, close, where),
            _holdings(book, close, where),
        ),
    )


def _elutions(book: Book, day: dt.date, tz: ZoneInfo) -> Section:
    tests = BreakthroughRepository(book)
    rows = []
    for elution in ElutionRepository(book).on_day(day, tz):
        reading = tests.find(elution.id)
        moly = "untested" if reading is None else f"moly {reading.ratio:.4f}"
        rows.append(
            f"{elution.id} {elution.generator_id} {stamp(elution.drawn_at, tz)} "
            f"{elution.activity.format('mci', 1)} in {elution.volume} "
            f"yield {elution.efficiency * Decimal(100):.1f}% {moly}"
        )
    return Section("elutions", tuple(rows), "no column was milked")


def _batches(book: Book, day: dt.date, tz: ZoneInfo) -> Section:
    rows = []
    for batch in BatchRepository(book).on_day(day, tz):
        purity = "no strips yet" if batch.rcp is None else f"rcp {batch.rcp}%"
        rows.append(
            f"{batch.id} {batch.code} {stamp(batch.made_at, tz)} "
            f"{batch.activity.format('mci', 1)} in {batch.volume} {purity}"
        )
    return Section("batches", tuple(rows), "nothing was compounded")


def _doses(book: Book, day: dt.date, tz: ZoneInfo) -> Section:
    orders = OrderRepository(book)
    rows = []
    for dose in DoseRepository(book).on_day(day, tz):
        order = orders.get(dose.order_id)
        rows.append(
            f"{dose.id} {order.customer_id} {order.patient_ref} {dose.code} "
            f"{order.activity.format('mci', 1)} at {stamp(order.calibration_at, tz)} "
            f"drawn {dose.volume} off {dose.batch_id} "
            f"({dose.variance_from(order.activity):+}%)"
        )
    return Section("doses", tuple(rows), "nothing was drawn")


def _shipments(book: Book, day: dt.date, tz: ZoneInfo) -> Section:
    rows = []
    for box in ShipmentRepository(book).on_day(day, tz):
        signed = (
            "on the dock"
            if box.delivered_at is None
            else f"signed {box.received_by} {stamp(box.delivered_at, tz)}"
        )
        rows.append(
            f"{box.id} {box.customer_id} {box.label.value} TI {box.transport_index} "
            f"{box.dose_count} doses {signed}"
        )
    return Section("shipments", tuple(rows), "nothing left the dock")


def _survey(book: Book, day: dt.date, tz: ZoneInfo) -> Section:
    service = SurveyService(book, tz)
    missed = service.areas_missed(day)
    rows = []
    if missed:
        rows.append("areas not surveyed: " + ", ".join(area.value for area in missed))
    worst = service.worst_area_on(day)
    if worst is not None:
        rows.append(f"hottest reading {worst[0].value} {worst[1]}")
    for failure in service.open_failures():
        rows.append(f"open contamination {failure.note()}")
    return Section("survey", tuple(rows), "surveyed clean")


def _waste(book: Book, close: dt.datetime, tz: ZoneInfo) -> Section:
    service = WasteService(book, tz)
    rows = [one.note() for one in service.held(close)]
    ready = service.ready(close)
    rows.extend(f"{one.id} ready to survey out" for one in ready)
    return Section("waste store", tuple(rows), "nothing in the store")


def _holdings(book: Book, close: dt.datetime, tz: ZoneInfo) -> Section:
    rows = []
    for check in InventoryService(book, tz).check(close):
        share = "no limit on file" if check.share is None else f"{check.share * 100:.1f}% of limit"
        rows.append(f"{check.holding.symbol} {check.holding.total.format('mci', 1)} {share}")
    return Section("on the premises at midnight", tuple(rows), "nothing on the premises")
