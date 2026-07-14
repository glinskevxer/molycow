"""Taking an order, and refusing the ones the pharmacy is not allowed to fill.

Three questions have to be answered before an order is written down. Is the
hospital still on the books. Is the physician still named on their licence for
this nuclide. Is what they asked for a dose of this product at all. None of
them are the pharmacy's judgement to make later, so they are all made here.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import RuleError
from molycow.formulary import formula
from molycow.model.order import Order, OrderState, Priority
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.orders import OrderRepository
from molycow.store.register import AuthorizedUserRepository, CustomerRepository
from molycow.units import Activity


@dataclass(frozen=True)
class Refusal:
    """Why an order could not be taken, in the words the phone call needs."""

    rule: str
    reason: str


class OrderService:
    """The order desk."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._orders = OrderRepository(book)
        self._customers = CustomerRepository(book)
        self._users = AuthorizedUserRepository(book)
        self._audit = AuditRepository(book)

    def refusal_for(
        self,
        customer_id: str,
        user_id: str,
        code: str,
        activity: Activity,
        calibration_at: dt.datetime,
    ) -> Refusal | None:
        """Whether this order may be taken, without writing anything down."""
        monograph = formula(code)
        customer = self._customers.get(customer_id)
        day = day_of(calibration_at, self._tz)
        if not customer.is_open_on(day):
            return Refusal("customer-open", "that customer is not on the books that day")
        if not customer.may_receive(monograph.nuclide):
            return Refusal("customer-nuclide", "that customer may not receive that nuclide")
        user = self._users.get(user_id)
        if user.customer_id != customer_id:
            return Refusal("user-customer", "that physician is not named at that customer")
        if not user.is_current_on(day):
            return Refusal("user-current", "that physician is not current that day")
        if not user.may_order(monograph.nuclide):
            return Refusal("user-nuclide", "that physician is not named for that nuclide")
        if not monograph.dose_fits(activity):
            return Refusal("dose-range", "that is not an adult dose of that product")
        return None

    def take(
        self,
        customer_id: str,
        user_id: str,
        code: str,
        procedure: str,
        patient_ref: str,
        activity: Activity,
        calibration_at: dt.datetime,
        ordered_at: dt.datetime,
        priority: Priority = Priority.ROUTINE,
    ) -> Order:
        """Write an order into the book."""
        refused = self.refusal_for(customer_id, user_id, code, activity, calibration_at)
        if refused is not None:
            raise RuleError(refused.rule, refused.reason, customer=customer_id, kit=code)
        order = Order(
            id=self._orders.next_id(day_of(ordered_at, self._tz)),
            customer_id=customer_id,
            user_id=user_id,
            code=formula(code).code,
            procedure=procedure,
            patient_ref=patient_ref,
            activity=activity,
            calibration_at=calibration_at,
            ordered_at=ordered_at,
            priority=priority,
        )
        with self._book.atomic():
            self._orders.add(order)
        return order

    def cancel(self, order_id: str) -> Order:
        """Take an order off the list, which only works while it is open."""
        order = self._orders.get(order_id)
        if not order.is_open():
            raise RuleError(
                "order-final",
                "that order has already been finished",
                order=order_id,
                state=order.state.value,
            )
        with self._book.atomic():
            return self._orders.save_state(order.cancelled())

    def amend(
        self,
        order_id: str,
        at: dt.datetime,
        by: str,
        activity: Activity | None = None,
        calibration_at: dt.datetime | None = None,
    ) -> Order:
        """Change what an open order asks for, against the same rules as taking it."""
        order = self._orders.get(order_id)
        if not order.is_open():
            raise RuleError(
                "order-final",
                "that order has already been finished",
                order=order_id,
                state=order.state.value,
            )
        wanted = activity or order.activity
        when = calibration_at or order.calibration_at
        refused = self.refusal_for(order.customer_id, order.user_id, order.code, wanted, when)
        if refused is not None:
            raise RuleError(refused.rule, refused.reason, order=order_id)
        amended = order.amended(wanted, when)
        with self._book.atomic():
            self._orders.save_amendment(amended)
            self._audit.record(
                at,
                by,
                "amended",
                order_id,
                f"{amended.activity.format('mci', 1)} at {when:%Y-%m-%d %H:%M}",
            )
        return amended

    def due_on(self, day: dt.date) -> list[Order]:
        return [one for one in self._orders.due_on(day, self._tz) if one.is_open()]

    def worklist(self, at: dt.datetime, hours: int = 4) -> list[Order]:
        """Open orders to work now: stat first, then the next few hours by time.

        A stat order is on the list whether or not its calibration time falls
        inside the window, because the point of marking one stat is that it
        does not wait for the window to come round.
        """
        window = at + dt.timedelta(hours=hours)
        due = [one for one in self._orders.due_between(at, window) if one.state is OrderState.OPEN]
        waiting = [one for one in self._orders.stat_orders() if one not in due]
        return sorted([*due, *waiting], key=lambda one: one.queue_key)

    def late(self, at: dt.datetime) -> list[Order]:
        return self._orders.late_at(at)
