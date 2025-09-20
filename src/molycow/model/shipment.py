"""A package on the dock, and the paperwork that goes with it.

A shipment is one box for one customer. It carries the doses that were packed
into it, the two meter readings taken after it was closed, and, once the
courier has been, who signed for it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.nuclides import nuclide
from molycow.transport import Label, a2_fraction, label_for, transport_index
from molycow.units import Activity


@dataclass(frozen=True)
class Shipment:
    """One box, closed and read."""

    id: str
    customer_id: str
    packed_at: dt.datetime
    packed_by: str
    dose_ids: tuple[str, ...]
    symbol: str
    activity: Activity
    surface_mrem: Decimal
    metre_mrem: Decimal
    delivered_at: dt.datetime | None = None
    received_by: str | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.SHIPMENT)
        expect(self.customer_id, Kind.CUSTOMER)
        object.__setattr__(self, "symbol", nuclide(self.symbol).symbol)
        if not self.dose_ids:
            raise ValidationError("an empty box is not a shipment", id=self.id)
        for dose_id in self.dose_ids:
            expect(dose_id, Kind.DOSE)
        if len(set(self.dose_ids)) != len(self.dose_ids):
            raise ValidationError("a dose cannot be packed twice", id=self.id)
        if not self.packed_by.strip():
            raise ValidationError("a shipment is signed by whoever packed it", id=self.id)
        if self.activity.is_zero():
            raise ValidationError("a shipment with no activity in it is not one", id=self.id)
        if self.delivered_at is not None and self.delivered_at < self.packed_at:
            raise ValidationError("that shipment was delivered before it was packed", id=self.id)
        label_for(self.surface_mrem, self.metre_mrem)

    @property
    def label(self) -> Label:
        return label_for(self.surface_mrem, self.metre_mrem)

    @property
    def transport_index(self) -> Decimal:
        return transport_index(self.metre_mrem)

    @property
    def a2_fraction(self) -> Decimal:
        return a2_fraction(self.symbol, self.activity)

    @property
    def is_delivered(self) -> bool:
        return self.delivered_at is not None

    @property
    def dose_count(self) -> int:
        return len(self.dose_ids)

    def holds(self, dose_id: str) -> bool:
        return dose_id in self.dose_ids

    def delivered(self, at: dt.datetime, received_by: str) -> Shipment:
        """The same shipment with the courier's signature on it."""
        if self.is_delivered:
            raise ValidationError("that shipment has already been delivered", id=self.id)
        if not received_by.strip():
            raise ValidationError("a delivery is signed for", id=self.id)
        return Shipment(
            id=self.id,
            customer_id=self.customer_id,
            packed_at=self.packed_at,
            packed_by=self.packed_by,
            dose_ids=self.dose_ids,
            symbol=self.symbol,
            activity=self.activity,
            surface_mrem=self.surface_mrem,
            metre_mrem=self.metre_mrem,
            delivered_at=at,
            received_by=received_by,
        )

    def manifest_line(self) -> str:
        """The line the driver's manifest carries for this box."""
        return (
            f"{self.id} {self.customer_id} {self.label.value} "
            f"TI {self.transport_index} {self.dose_count} doses "
            f"{self.activity.format('mci', 1)} {self.symbol}"
        )
