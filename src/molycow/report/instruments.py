"""The instrument board: what is due, what is overdue, and what failed.

An instrument does not stop working on the day its calibration runs out; it
stops being something anybody can stand behind. This is the sheet that gets
looked at on a Monday, so the answer is always what is due this week rather
than what happened last quarter.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from molycow.clock import stamp, zone
from molycow.model.qc import CheckKind
from molycow.report.sheet import Section, Sheet
from molycow.service.qc import QcService
from molycow.store.book import Book
from molycow.store.instruments import CheckSourceRepository, InstrumentRepository, QcRepository


def instrument_sheet(book: Book, day: dt.date, tz: ZoneInfo | None = None) -> Sheet:
    """The board for one day."""
    where = tz or zone()
    service = QcService(book, where)
    instruments = InstrumentRepository(book)
    checks = QcRepository(book)
    sources = CheckSourceRepository(book)
    rows = []
    overdue = []
    for instrument in instruments.all():
        unusable = instrument.unusable_reason(day)
        state = unusable or "in service"
        last = checks.last(instrument.id, CheckKind.CONSTANCY)
        seen = "never checked" if last is None else stamp(last.at, where)
        rows.append(
            f"{instrument.id}  {instrument.kind.value:16} {instrument}  "
            f"calibration due {instrument.calibration_due}  last constancy {seen}  {state}"
        )
        for kind in service.overdue(instrument.id, day):
            overdue.append(f"{instrument.id}  {kind.value} overdue")
    failures = [
        f"{stamp(one.at, where)}  {one.instrument_id}  {one.note()}" for one in service.failures()
    ]
    on_the_shelf = [
        f"{one.serial}  {one.symbol:7} reads {one.activity_on(day).format('uci', 1)}"
        for one in sources.in_use_on(day)
    ]
    return Sheet(
        title=f"instruments {day.isoformat()}",
        sections=(
            Section("instruments", tuple(rows), "no instruments on the books"),
            Section("overdue", tuple(overdue), "nothing is overdue"),
            Section("failed checks", tuple(failures), "no check has failed"),
            Section("sources", tuple(on_the_shelf), "no sealed sources"),
        ),
    )
