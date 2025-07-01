"""Drawing a syringe against an order.

The volume is worked out backwards. The order wants an activity at a moment,
so the syringe needs whatever will decay to that by then, and the volume is
that activity divided by what the batch holds per millilitre right now.

Both halves of that division decay at the same rate, so the volume comes out
the same whether the dose is drawn at seven or at half past eight. What changes
is the number on the assay, not the number of millilitres, and a bench that
expects a bigger volume later in the morning is a bench that is about to draw
the wrong syringe out of a batch someone topped up.

The assay is the technologist's own measurement of what they drew, and it is
compared against the order, not against the plan. A plan that says 0.55 mL and
a syringe that reads twenty percent light is a syringe that goes back.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.decay import needed_at
from molycow.errors import ReleaseError, RuleError
from molycow.model.dose import TOLERANCE_PERCENT, Dose
from molycow.model.kit import Batch
from molycow.model.order import Order
from molycow.nuclides import nuclide
from molycow.service.purity import PurityService
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.kits import BatchRepository
from molycow.store.orders import OrderRepository
from molycow.units import Activity, Volume


@dataclass(frozen=True)
class DrawPlan:
    """What the bench should pull, worked out before the syringe is filled."""

    order: Order
    batch: Batch
    drawn_at: dt.datetime
    needed: Activity
    volume: Volume

    @property
    def label_activity(self) -> Activity:
        return self.order.activity


class DispenseService:
    """The dispensing bench."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._orders = OrderRepository(book)
        self._batches = BatchRepository(book)
        self._doses = DoseRepository(book)
        self._purity = PurityService(book)

    def drawn_from(self, batch_id: str) -> Volume:
        taken = Volume.zero()
        for dose in self._doses.for_batch(batch_id):
            taken = taken + dose.volume
        return taken

    def remaining_in(self, batch_id: str) -> Volume:
        batch = self._batches.get(batch_id)
        return batch.volume - self.drawn_from(batch_id)

    def plan(self, order_id: str, batch_id: str, at: dt.datetime) -> DrawPlan:
        """Work the draw out without filling anything."""
        order = self._orders.get(order_id)
        if not order.is_open():
            raise RuleError(
                "order-final", "that order is not open", order=order_id, state=order.state.value
            )
        batch = self._purity.require_released(batch_id, at)
        if batch.code != order.code:
            raise RuleError(
                "batch-product",
                "that batch is not the product the order asked for",
                order=order_id,
                ordered=order.code,
                batch=batch.code,
            )
        if at > order.calibration_at:
            raise RuleError(
                "order-late",
                "that calibration time has already gone by",
                order=order_id,
            )
        needed = needed_at(order.activity, nuclide(order.nuclide), order.calibration_at, at)
        volume = batch.concentration_at(at).volume_for(needed)
        left = self.remaining_in(batch_id)
        if volume > left:
            raise RuleError(
                "batch-short",
                "there is not enough left in that batch",
                batch=batch_id,
                wanted=str(volume),
                left=str(left),
            )
        return DrawPlan(order, batch, at, needed, volume)

    def draw(
        self,
        order_id: str,
        batch_id: str,
        at: dt.datetime,
        assayed: Activity,
        drawn_by: str,
        volume: Volume | None = None,
        tolerance: Decimal = TOLERANCE_PERCENT,
    ) -> Dose:
        """Fill the syringe, assay it, and close the order."""
        planned = self.plan(order_id, batch_id, at)
        drawn_volume = volume if volume is not None else planned.volume
        if drawn_volume > self.remaining_in(batch_id):
            raise RuleError(
                "batch-short",
                "there is not enough left in that batch",
                batch=batch_id,
                wanted=str(drawn_volume),
                left=str(self.remaining_in(batch_id)),
            )
        dose = Dose(
            id=self._doses.next_id(day_of(at, self._tz)),
            order_id=order_id,
            batch_id=batch_id,
            code=planned.order.code,
            drawn_at=at,
            calibration_at=planned.order.calibration_at,
            volume=drawn_volume,
            assayed=assayed,
            drawn_by=drawn_by,
        )
        if not dose.within_tolerance(planned.order.activity, tolerance):
            raise ReleaseError(
                "dose-tolerance",
                "that syringe does not assay close enough to the order",
                order=order_id,
                variance=f"{dose.variance_from(planned.order.activity)}%",
            )
        with self._book.atomic():
            self._doses.add(dose)
            self._orders.save_state(planned.order.filled())
        return dose

    def for_order(self, order_id: str) -> Dose | None:
        return self._doses.for_order(order_id)

    def drawn_on(self, day: dt.date) -> list[Dose]:
        return self._doses.on_day(day, self._tz)

    def batches_for(self, order_id: str, at: dt.datetime) -> list[Batch]:
        """The batches on the bench that could fill an order right now."""
        order = self._orders.get(order_id)
        ready = []
        for batch in self._batches.in_date_at(at, order.code):
            if batch.hold_reason(at) is not None:
                continue
            try:
                self.plan(order_id, batch.id, at)
            except (RuleError, ReleaseError):
                continue
            ready.append(batch)
        return ready
