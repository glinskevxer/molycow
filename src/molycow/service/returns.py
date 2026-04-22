"""A syringe that came back, and what happens to it.

A dose that was not injected is still a dose: it has a patient reference on it,
it was on somebody's licence for an afternoon, and it comes back with activity
in it. It is written down as returned, and it goes into a decay container at
whatever it reads when it arrives, not at what the label said this morning.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import NotFoundError, RuleError
from molycow.formulary import formula
from molycow.model.dose import Dose, DoseReturn
from molycow.model.waste import ContainerKind
from molycow.service.waste import WasteService
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.orders import OrderRepository
from molycow.store.returns import ReturnRepository
from molycow.store.shipments import ShipmentRepository
from molycow.units import Activity


@dataclass(frozen=True)
class Returned:
    """One dose that came back."""

    dose: Dose
    returned_at: dt.datetime
    reason: str
    received_by: str
    container_id: str | None

    @property
    def activity_back(self) -> Activity:
        """What was in the syringe when it arrived back."""
        return self.dose.activity_at(self.returned_at)

    def line(self) -> str:
        """The line the returns list prints."""
        where = self.container_id or "not put away"
        return f"{self.dose.id}  {self.activity_back.format('mci', 2):>12}  {self.reason}  {where}"


class ReturnService:
    """The returns bench."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._doses = DoseRepository(book)
        self._orders = OrderRepository(book)
        self._shipments = ShipmentRepository(book)
        self._returns = ReturnRepository(book)
        self._waste = WasteService(book, self._tz)
        self._audit = AuditRepository(book)

    def take_back(self, dose_id: str, at: dt.datetime, reason: str, received_by: str) -> Returned:
        """Book a syringe back in and put it in a decay container."""
        dose = self._doses.get(dose_id)
        if at < dose.drawn_at:
            raise RuleError("return-early", "that dose had not been drawn yet", dose=dose_id)
        if not reason.strip():
            raise RuleError("return-reason", "a return says why", dose=dose_id)
        if self.find(dose_id) is not None:
            raise RuleError("return-twice", "that dose is already back", dose=dose_id)
        box = self._shipments.holding(dose_id)
        if box is None:
            raise RuleError("return-unsent", "that dose never left the building", dose=dose_id)
        with self._book.atomic():
            container = self._waste.container_for(ContainerKind.SHARPS, at)
            self._waste.discard(
                container.id,
                formula(dose.code).nuclide,
                dose.activity_at(at),
                at,
                dose.id,
            )
            self._returns.add(
                DoseReturn(
                    dose_id=dose_id,
                    returned_at=at,
                    reason=reason,
                    received_by=received_by,
                    container_id=container.id,
                )
            )
            self._audit.record(at, received_by, "discarded", dose_id, f"returned: {reason}")
        return Returned(dose, at, reason, received_by, container.id)

    def find(self, dose_id: str) -> Returned | None:
        """One return, if that syringe came back."""
        record = self._returns.find(dose_id)
        if record is None:
            return None
        return self._joined(record)

    def _joined(self, record: DoseReturn) -> Returned:
        return Returned(
            dose=self._doses.get(record.dose_id),
            returned_at=record.returned_at,
            reason=record.reason,
            received_by=record.received_by,
            container_id=record.container_id,
        )

    def get(self, dose_id: str) -> Returned:
        """One return, or a refusal if that syringe is still out."""
        found = self.find(dose_id)
        if found is None:
            raise NotFoundError("that dose has not come back", dose=dose_id)
        return found

    def all(self) -> list[Returned]:
        """Every syringe that came back, oldest first."""
        return [self._joined(one) for one in self._returns.all()]

    def for_customer(self, customer_id: str) -> list[Returned]:
        """Everything one hospital sent back."""
        found = []
        for one in self.all():
            order = self._orders.get(one.dose.order_id)
            if order.customer_id == customer_id:
                found.append(one)
        return found

    def unused_activity(self, at: dt.datetime) -> Activity:
        """What the returns are worth, added up at a moment."""
        total = Activity.zero()
        for one in self.all():
            total = total + one.dose.activity_at(at)
        return total
