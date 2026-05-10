"""What a month looked like, for the people who do not work in the hot lab.

A day sheet answers what happened. A period report answers whether the
pharmacy is working: how many doses went out, how much of what was made was
actually used, how the columns are yielding, and which customer is taking
which share of the work.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import combine, day_of, zone
from molycow.report.sheet import Section, Sheet
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.generators import ElutionRepository
from molycow.store.kits import BatchRepository
from molycow.store.orders import OrderRepository
from molycow.store.returns import ReturnRepository
from molycow.units import Activity


@dataclass(frozen=True)
class Period:
    """A run of days, from the first to the last inclusive."""

    first: dt.date
    last: dt.date

    def holds(self, day: dt.date) -> bool:
        return self.first <= day <= self.last

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    def __str__(self) -> str:
        return f"{self.first.isoformat()} to {self.last.isoformat()}"


def month(year: int, number: int) -> Period:
    """The period covering one calendar month."""
    first = dt.date(year, number, 1)
    if number == 12:
        last = dt.date(year, 12, 31)
    else:
        last = dt.date(year, number + 1, 1) - dt.timedelta(days=1)
    return Period(first, last)


def period_sheet(book: Book, over: Period, tz: ZoneInfo | None = None) -> Sheet:
    """Build the period report."""
    where = tz or zone()
    return Sheet(
        title=f"period report {over}",
        sections=(
            _work(book, over, where),
            _yields(book, over, where),
            _customers(book, over, where),
            _returns(book, over, where),
        ),
    )


def _in_period(moment: dt.datetime, over: Period, tz: ZoneInfo) -> bool:
    return over.holds(day_of(moment, tz))


def _work(book: Book, over: Period, tz: ZoneInfo) -> Section:
    elutions = [one for one in ElutionRepository(book).all() if _in_period(one.drawn_at, over, tz)]
    batches = [one for one in BatchRepository(book).all() if _in_period(one.made_at, over, tz)]
    doses = [one for one in DoseRepository(book).all() if _in_period(one.drawn_at, over, tz)]
    made = Activity.zero()
    for batch in batches:
        made = made + batch.activity
    drawn = Activity.zero()
    for dose in doses:
        drawn = drawn + dose.assayed
    rows = [
        f"{over.days} days",
        f"{len(elutions)} elutions",
        f"{len(batches)} batches, {made.format('ci', 3)} compounded",
        f"{len(doses)} doses, {drawn.format('ci', 3)} drawn",
    ]
    if not made.is_zero():
        used = (drawn.uci / made.uci * Decimal(100)).quantize(Decimal("0.1"))
        rows.append(f"{used}% of what was compounded went into a syringe")
    return Section("work", tuple(rows), "nothing happened in that period")


def _yields(book: Book, over: Period, tz: ZoneInfo) -> Section:
    elutions = [one for one in ElutionRepository(book).all() if _in_period(one.drawn_at, over, tz)]
    if not elutions:
        return Section("column yields", (), "no column was milked")
    shares = [one.efficiency for one in elutions]
    worst = min(elutions, key=lambda one: one.efficiency)
    average = sum(shares, Decimal(0)) / Decimal(len(shares)) * Decimal(100)
    rows = [
        f"average yield {average.quantize(Decimal('0.1'))}%",
        f"worst {worst.id} at {(worst.efficiency * Decimal(100)).quantize(Decimal('0.1'))}%",
    ]
    return Section("column yields", tuple(rows))


def _customers(book: Book, over: Period, tz: ZoneInfo) -> Section:
    orders = OrderRepository(book)
    doses = [one for one in DoseRepository(book).all() if _in_period(one.drawn_at, over, tz)]
    by_customer: dict[str, list[Activity]] = {}
    for dose in doses:
        customer = orders.get(dose.order_id).customer_id
        by_customer.setdefault(customer, []).append(dose.assayed)
    rows = []
    for customer, activities in sorted(by_customer.items()):
        total = Activity.zero()
        for one in activities:
            total = total + one
        rows.append(f"{customer}  {len(activities):4d} doses  {total.format('mci', 1)}")
    return Section("customers", tuple(rows), "nobody was sent anything")


def _returns(book: Book, over: Period, tz: ZoneInfo) -> Section:
    came_back = [
        one for one in ReturnRepository(book).all() if _in_period(one.returned_at, over, tz)
    ]
    rows = [f"{one.dose_id}  {one.reason}" for one in came_back]
    return Section("returns", tuple(rows), "nothing came back")


def month_of(day: dt.date) -> Period:
    """The month a day falls in."""
    return month(day.year, day.month)


def midnight_after(over: Period, tz: ZoneInfo | None = None) -> dt.datetime:
    """The end of the period, for anything that has to be read at a moment."""
    return combine(over.last, dt.time(23, 59), tz or zone())
