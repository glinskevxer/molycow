"""Reading and writing the order book.

The table is ``customer_order`` rather than ``order``, which is a reserved word
in sql and reads badly in every query that has to quote it.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.ids import Kind, make, next_serial
from molycow.model.order import Order, OrderState, Priority
from molycow.store.records import Records
from molycow.store.rows import activity_in, activity_out, moment_in, moment_out, text_in


def order_from(row: sqlite3.Row) -> Order:
    """Build a order out of a row of the table."""
    return Order(
        id=text_in(row, "id"),
        customer_id=text_in(row, "customer_id"),
        user_id=text_in(row, "user_id"),
        code=text_in(row, "code"),
        procedure=text_in(row, "procedure"),
        patient_ref=text_in(row, "patient_ref"),
        activity=activity_in(row["activity"], "activity"),
        calibration_at=moment_in(row["calibration_at"], "calibration_at"),
        ordered_at=moment_in(row["ordered_at"], "ordered_at"),
        state=OrderState(text_in(row, "state")),
        priority=Priority(text_in(row, "priority")),
    )


class OrderRepository(Records):
    """Everything the hospitals have asked for."""

    def add(self, order: Order) -> Order:
        self._book.execute(
            """
            INSERT INTO customer_order
              (id, customer_id, user_id, code, procedure, patient_ref,
               activity, calibration_at, ordered_at, state, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.id,
                order.customer_id,
                order.user_id,
                order.code,
                order.procedure,
                order.patient_ref,
                activity_out(order.activity),
                moment_out(order.calibration_at),
                moment_out(order.ordered_at),
                order.state.value,
                order.priority.value,
            ),
        )
        return order

    def find(self, order_id: str) -> Order | None:
        row = self._book.one("SELECT * FROM customer_order WHERE id = ?", (order_id,))
        return None if row is None else order_from(row)

    def get(self, order_id: str) -> Order:
        """One order, or a refusal if it is not in the book."""
        return self.required(self.find(order_id), "no such order", id=order_id)

    def all(self) -> list[Order]:
        rows = self._book.all("SELECT * FROM customer_order ORDER BY calibration_at, id")
        return [order_from(row) for row in rows]

    def open_orders(self) -> list[Order]:
        rows = self._book.all(
            "SELECT * FROM customer_order WHERE state = ? ORDER BY calibration_at, id",
            (OrderState.OPEN.value,),
        )
        return [order_from(row) for row in rows]

    def for_customer(self, customer_id: str, state: OrderState | None = None) -> list[Order]:
        rows = self._book.all(
            "SELECT * FROM customer_order WHERE customer_id = ? ORDER BY calibration_at, id",
            (customer_id,),
        )
        found = [order_from(row) for row in rows]
        if state is not None:
            found = [one for one in found if one.state is state]
        return found

    def due_on(self, day: dt.date, tz: ZoneInfo | None = None) -> list[Order]:
        """Orders whose calibration time falls on a local day."""
        where = tz or zone()
        return [one for one in self.all() if day_of(one.calibration_at, where) == day]

    def due_between(self, start: dt.datetime, end: dt.datetime) -> list[Order]:
        rows = self._book.all(
            """
            SELECT * FROM customer_order
            WHERE calibration_at >= ? AND calibration_at <= ?
            ORDER BY calibration_at, id
            """,
            (moment_out(start), moment_out(end)),
        )
        return [order_from(row) for row in rows]

    def stat_orders(self) -> list[Order]:
        """The open stat orders, soonest first."""
        rows = self._book.all(
            """
            SELECT * FROM customer_order
            WHERE priority = ? AND state = ?
            ORDER BY calibration_at, id
            """,
            (Priority.STAT.value, OrderState.OPEN.value),
        )
        return [order_from(row) for row in rows]

    def late_at(self, moment: dt.datetime) -> list[Order]:
        return [one for one in self.open_orders() if one.is_late_at(moment)]

    def save_state(self, order: Order) -> Order:
        """Write a state change that the model has already checked."""
        self._book.execute(
            "UPDATE customer_order SET state = ? WHERE id = ?",
            (order.state.value, order.id),
        )
        return order

    def next_id(self, day: dt.date) -> str:
        issued = [str(row["id"]) for row in self._book.all("SELECT id FROM customer_order")]
        return make(Kind.ORDER, next_serial(issued, Kind.ORDER, day), day)

    def count(self, state: OrderState | None = None) -> int:
        if state is None:
            return int(self._book.value("SELECT count(*) FROM customer_order") or 0)
        value = self._book.value(
            "SELECT count(*) FROM customer_order WHERE state = ?", (state.value,)
        )
        return int(value or 0)
