"""One customer's month, the way the hospital's own office asks for it.

A statement is not a sales document. It is the list a nuclear medicine
department checks against their own records: what was ordered, what was drawn
for it, what came back, and which orders the pharmacy never filled. The last
of those is the one they actually telephone about.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, stamp, zone
from molycow.model.order import Order, OrderState
from molycow.report.period import Period
from molycow.report.sheet import Section, Sheet
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.orders import OrderRepository
from molycow.store.register import CustomerRepository
from molycow.store.returns import ReturnRepository
from molycow.units import Activity


@dataclass(frozen=True)
class Line:
    """One order and whatever became of it."""

    order: Order
    drawn: Activity | None
    came_back: bool

    @property
    def was_filled(self) -> bool:
        return self.drawn is not None

    def row(self, tz: ZoneInfo) -> str:
        """The row the statement prints."""
        state = self.order.state.value
        if self.came_back:
            state = "returned"
        drawn = "not filled" if self.drawn is None else self.drawn.format("mci", 1)
        return (
            f"{stamp(self.order.calibration_at, tz)}  {self.order.id}  "
            f"{self.order.patient_ref:12} {self.order.code:7} "
            f"{self.order.activity.format('mci', 1):>10} ordered  {drawn:>12} drawn  {state}"
        )


def lines_for(book: Book, customer_id: str, over: Period, tz: ZoneInfo) -> list[Line]:
    """Every order for a customer inside a period, with what became of it."""
    doses = DoseRepository(book)
    returned = {one.dose_id for one in ReturnRepository(book).all()}
    found: list[Line] = []
    for order in OrderRepository(book).for_customer(customer_id):
        if not over.holds(day_of(order.calibration_at, tz)):
            continue
        dose = doses.for_order(order.id)
        found.append(
            Line(
                order=order,
                drawn=None if dose is None else dose.assayed,
                came_back=dose is not None and dose.id in returned,
            )
        )
    return found


def statement(book: Book, customer_id: str, over: Period, tz: ZoneInfo | None = None) -> Sheet:
    """Build one customer's statement for a period."""
    where = tz or zone()
    customer = CustomerRepository(book).get(customer_id)
    lines = lines_for(book, customer_id, over, where)
    filled = [one for one in lines if one.was_filled]
    total = Activity.zero()
    for one in filled:
        assert one.drawn is not None
        total = total + one.drawn
    unfilled = [
        one for one in lines if not one.was_filled and one.order.state is not OrderState.CANCELLED
    ]
    cancelled = [one for one in lines if one.order.state is OrderState.CANCELLED]
    summary = [
        f"{len(lines)} orders",
        f"{len(filled)} filled, {total.format('mci', 1)} drawn",
        f"{len(unfilled)} not filled",
        f"{len(cancelled)} cancelled",
        f"{len([one for one in lines if one.came_back])} came back",
    ]
    if lines:
        share = Decimal(len(filled)) / Decimal(len(lines)) * Decimal(100)
        summary.append(f"{share.quantize(Decimal('0.1'))}% of the orders were filled")
    return Sheet(
        title=f"statement {customer.name} {over}",
        sections=(
            Section("summary", tuple(summary), "nothing was ordered"),
            Section(
                "orders",
                tuple(one.row(where) for one in lines),
                "no orders in that period",
            ),
            Section(
                "not filled",
                tuple(one.order.id for one in unfilled),
                "everything was filled",
            ),
        ),
    )
