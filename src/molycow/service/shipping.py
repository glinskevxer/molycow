"""Packing a box for one customer and getting it onto the courier.

The activity written on the outside is the activity at the moment the box was
closed, decayed from each syringe's own assay. It is not the sum of the labels,
because the labels are calibrated for scan times that have not happened yet.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import RuleError
from molycow.formulary import formula
from molycow.model.shipment import Shipment
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.orders import OrderRepository
from molycow.store.register import CustomerRepository
from molycow.store.shipments import ShipmentRepository
from molycow.transport import fits_type_a
from molycow.units import Activity


@dataclass(frozen=True)
class Manifest:
    """What the driver takes out, and what it adds up to."""

    day: dt.date
    shipments: tuple[Shipment, ...]

    @property
    def vehicle_index(self) -> Decimal:
        return sum((one.transport_index for one in self.shipments), Decimal(0)).quantize(
            Decimal("0.1")
        )

    @property
    def dose_count(self) -> int:
        return sum(one.dose_count for one in self.shipments)

    def lines(self) -> list[str]:
        return [one.manifest_line() for one in self.shipments]


class ShippingService:
    """The dock."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._shipments = ShipmentRepository(book)
        self._doses = DoseRepository(book)
        self._orders = OrderRepository(book)
        self._customers = CustomerRepository(book)
        self._audit = AuditRepository(book)

    def ready_for(self, customer_id: str, at: dt.datetime) -> list[str]:
        """Doses drawn for a customer that are not in a box yet."""
        ready = []
        for dose in self._doses.all():
            order = self._orders.get(dose.order_id)
            if order.customer_id != customer_id:
                continue
            if self._shipments.holding(dose.id) is not None:
                continue
            if dose.drawn_at > at:
                continue
            ready.append(dose.id)
        return ready

    def pack(
        self,
        customer_id: str,
        dose_ids: list[str],
        at: dt.datetime,
        packed_by: str,
        surface_mrem: Decimal,
        metre_mrem: Decimal,
    ) -> Shipment:
        """Close a box and read it."""
        customer = self._customers.get(customer_id)
        if not dose_ids:
            raise RuleError("shipment-empty", "there is nothing to pack", customer=customer_id)
        total = Activity.zero()
        symbols: set[str] = set()
        for dose_id in dose_ids:
            dose = self._doses.get(dose_id)
            order = self._orders.get(dose.order_id)
            if order.customer_id != customer_id:
                raise RuleError(
                    "shipment-customer",
                    "that dose was drawn for another customer",
                    dose=dose_id,
                    customer=customer_id,
                )
            if self._shipments.holding(dose_id) is not None:
                raise RuleError("shipment-packed", "that dose is already in a box", dose=dose_id)
            if at < dose.drawn_at:
                raise RuleError("shipment-early", "that dose had not been drawn yet", dose=dose_id)
            symbols.add(formula(dose.code).nuclide)
            total = total + dose.activity_at(at)
        if len(symbols) > 1:
            raise RuleError(
                "shipment-mixed",
                "this pharmacy does not mix nuclides in one box",
                customer=customer_id,
                nuclides=", ".join(sorted(symbols)),
            )
        symbol = symbols.pop()
        if not fits_type_a(symbol, total):
            raise RuleError(
                "shipment-a2",
                "that box holds more than a Type A package may",
                customer=customer.id,
                activity=str(total),
            )
        shipment = Shipment(
            id=self._shipments.next_id(day_of(at, self._tz)),
            customer_id=customer_id,
            packed_at=at,
            packed_by=packed_by,
            dose_ids=tuple(dose_ids),
            symbol=symbol,
            activity=total,
            surface_mrem=surface_mrem,
            metre_mrem=metre_mrem,
        )
        with self._book.atomic():
            self._shipments.add(shipment)
            self._audit.record(
                at,
                packed_by,
                "packed",
                shipment.id,
                f"{shipment.dose_count} doses for {customer_id}",
            )
        return shipment

    def deliver(self, shipment_id: str, at: dt.datetime, received_by: str) -> Shipment:
        with self._book.atomic():
            signed = self._shipments.sign_for(shipment_id, at, received_by)
            self._audit.record(at, received_by, "delivered", shipment_id, "signed for")
        return signed

    def manifest(self, day: dt.date) -> Manifest:
        return Manifest(day, tuple(self._shipments.on_day(day, self._tz)))

    def outstanding(self) -> list[Shipment]:
        return self._shipments.undelivered()
