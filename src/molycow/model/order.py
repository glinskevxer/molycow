"""What a hospital asked for, and when they need it to read that activity.

An order names an activity and a calibration time, never a volume. The
calibration time is the moment the dose is meant to be injected, and it is the
only reason any of the decay arithmetic in this package exists.

No patient name is kept. The reference is whatever the ordering department put
on the request, usually an accession number, and that is all the pharmacy needs
to get the right syringe into the right lead pot.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from molycow.clock import hours_between
from molycow.errors import ValidationError
from molycow.formulary import Formula, formula
from molycow.ids import Kind, expect
from molycow.units import Activity

MAX_LEAD_HOURS = Decimal(72)


class Priority(Enum):
    """How far up the worklist an order sits."""

    ROUTINE = "routine"
    STAT = "stat"

    @property
    def jumps_the_queue(self) -> bool:
        """Whether it is worked before anything routine, whatever the clock says."""
        return self is Priority.STAT

    @property
    def notice_hours(self) -> Decimal:
        """The least notice this sort of order is normally given."""
        return Decimal(0) if self is Priority.STAT else Decimal(1)


class OrderState(Enum):
    """Where an order has got to."""

    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"

    @property
    def is_final(self) -> bool:
        return self is not OrderState.OPEN


@dataclass(frozen=True)
class Order:
    """One line on a hospital's morning request."""

    id: str
    customer_id: str
    user_id: str
    code: str
    procedure: str
    patient_ref: str
    activity: Activity
    calibration_at: dt.datetime
    ordered_at: dt.datetime
    state: OrderState = OrderState.OPEN
    priority: Priority = Priority.ROUTINE

    def __post_init__(self) -> None:
        expect(self.id, Kind.ORDER)
        expect(self.customer_id, Kind.CUSTOMER)
        expect(self.user_id, Kind.AUTHORIZED_USER)
        object.__setattr__(self, "code", formula(self.code).code)
        if not self.procedure.strip():
            raise ValidationError("an order needs the procedure it is for", id=self.id)
        if not self.patient_ref.strip():
            raise ValidationError("an order needs the department's reference", id=self.id)
        if self.activity.is_zero():
            raise ValidationError("an order for no activity is not an order", id=self.id)
        if self.calibration_at < self.ordered_at:
            raise ValidationError(
                "that calibration time has already gone by",
                id=self.id,
                calibration_at=self.calibration_at.isoformat(),
            )
        if self.lead_hours < self.priority.notice_hours:
            raise ValidationError(
                "a routine order needs an hour of notice, mark it stat",
                id=self.id,
                hours=str(self.lead_hours),
            )
        if hours_between(self.ordered_at, self.calibration_at) > MAX_LEAD_HOURS:
            raise ValidationError(
                "that calibration time is too far out to work to",
                id=self.id,
                hours=str(hours_between(self.ordered_at, self.calibration_at)),
            )

    @property
    def formula(self) -> Formula:
        return formula(self.code)

    @property
    def nuclide(self) -> str:
        return self.formula.nuclide

    @property
    def lead_hours(self) -> Decimal:
        """How much notice the pharmacy was given."""
        return hours_between(self.ordered_at, self.calibration_at)

    def is_open(self) -> bool:
        return self.state is OrderState.OPEN

    @property
    def is_stat(self) -> bool:
        return self.priority.jumps_the_queue

    @property
    def queue_key(self) -> tuple[int, dt.datetime]:
        """What the worklist sorts on: stat first, then by calibration time."""
        return (0 if self.is_stat else 1, self.calibration_at)

    def hours_to_calibration(self, at: dt.datetime) -> Decimal:
        return hours_between(at, self.calibration_at)

    def is_late_at(self, at: dt.datetime) -> bool:
        """Whether the calibration time has gone by with the order still open."""
        return self.is_open() and at > self.calibration_at

    def with_state(self, state: OrderState) -> Order:
        """The same order moved on, which only works once."""
        if self.state.is_final:
            raise ValidationError(
                "that order has already been finished",
                id=self.id,
                state=self.state.value,
            )
        return Order(
            id=self.id,
            customer_id=self.customer_id,
            user_id=self.user_id,
            code=self.code,
            procedure=self.procedure,
            patient_ref=self.patient_ref,
            activity=self.activity,
            calibration_at=self.calibration_at,
            ordered_at=self.ordered_at,
            state=state,
            priority=self.priority,
        )

    def amended(self, activity: Activity, calibration_at: dt.datetime) -> Order:
        """The same order with a new activity or a new time on it.

        A hospital moves a patient and telephones. That is an amendment, not a
        new order, because the old one has to stop existing: two open orders
        for one patient is how somebody gets two syringes.
        """
        if self.state.is_final:
            raise ValidationError(
                "that order has already been finished", id=self.id, state=self.state.value
            )
        return Order(
            id=self.id,
            customer_id=self.customer_id,
            user_id=self.user_id,
            code=self.code,
            procedure=self.procedure,
            patient_ref=self.patient_ref,
            activity=activity,
            calibration_at=calibration_at,
            ordered_at=self.ordered_at,
            state=self.state,
            priority=self.priority,
        )

    def filled(self) -> Order:
        return self.with_state(OrderState.FILLED)

    def cancelled(self) -> Order:
        return self.with_state(OrderState.CANCELLED)
