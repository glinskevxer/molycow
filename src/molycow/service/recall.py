"""Pulling a kit lot, and finding everything that came out of it.

A recall is not one record. The maker names a lot, and the pharmacy has to
work forwards from it: which batches were made from that box, which syringes
were drawn from those batches, which boxes those syringes went out in, and
which hospitals have to be telephoned. That chain is what this service walks.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.model.kit import Batch, KitLot
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.kits import BatchRepository, KitLotRepository
from molycow.store.orders import OrderRepository
from molycow.store.register import CustomerRepository
from molycow.store.shipments import ShipmentRepository


@dataclass(frozen=True)
class Reach:
    """Everything one recalled lot touched."""

    lot: KitLot
    batches: tuple[Batch, ...]
    dose_ids: tuple[str, ...]
    customers: tuple[str, ...]
    shipments: tuple[str, ...]
    telephone: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.batches

    def lines(self) -> list[str]:
        """The chain, as the telephone list it turns into."""
        out = [f"{self.lot.id} {self.lot.code} lot {self.lot.lot}"]
        out.extend(f"  batch {batch.id} made {batch.made_at:%Y-%m-%d}" for batch in self.batches)
        out.extend(f"  dose {dose_id}" for dose_id in self.dose_ids)
        out.extend(f"  telephone {line}" for line in self.telephone or self.customers)
        return out


class RecallService:
    """The chain from a maker's lot number to a telephone call."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._lots = KitLotRepository(book)
        self._batches = BatchRepository(book)
        self._doses = DoseRepository(book)
        self._orders = OrderRepository(book)
        self._shipments = ShipmentRepository(book)
        self._customers = CustomerRepository(book)
        self._audit = AuditRepository(book)

    def reach_of(self, lot_id: str) -> Reach:
        """What a lot touched, whether or not it has been recalled."""
        lot = self._lots.get(lot_id)
        batches = self._batches.for_kit_lot(lot_id)
        dose_ids: list[str] = []
        customers: list[str] = []
        shipments: list[str] = []
        for batch in batches:
            for dose in self._doses.for_batch(batch.id):
                dose_ids.append(dose.id)
                order = self._orders.get(dose.order_id)
                if order.customer_id not in customers:
                    customers.append(order.customer_id)
                box = self._shipments.holding(dose.id)
                if box is not None and box.id not in shipments:
                    shipments.append(box.id)
        return Reach(
            lot=lot,
            batches=tuple(batches),
            dose_ids=tuple(dose_ids),
            customers=tuple(customers),
            shipments=tuple(shipments),
            telephone=tuple(self._customers.get(one).contact() for one in customers),
        )

    def recall(self, lot_id: str, at: dt.datetime, reason: str, by: str) -> Reach:
        """Pull the lot, write it down, and give back what it touched."""
        with self._book.atomic():
            self._lots.recall(lot_id, at, reason)
            self._audit.record(at, by, "amended", lot_id, f"recalled: {reason}")
        return self.reach_of(lot_id)

    def recalled_lots(self) -> list[KitLot]:
        return self._lots.recalled()

    def batches_from_recalled(self) -> list[Batch]:
        """Every batch that came out of a lot that was later pulled."""
        found: list[Batch] = []
        for lot in self.recalled_lots():
            found.extend(self._batches.for_kit_lot(lot.id))
        return found
