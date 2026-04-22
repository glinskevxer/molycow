"""One syringe, drawn for one patient, calibrated for one moment.

The activity on the label is not the activity in the syringe. What is drawn is
whatever will have decayed to the ordered activity by the calibration time, so
a dose drawn at seven for a nine o'clock scan is a bigger number than the one
the department asked for. The assay is what the dose calibrator says the
syringe actually holds, and the tolerance is measured against the ordered
activity carried to the same moment.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from molycow.decay import decay_between
from molycow.errors import ValidationError
from molycow.formulary import Formula, formula
from molycow.ids import Kind, expect
from molycow.nuclides import nuclide
from molycow.units import Activity, Volume

TOLERANCE_PERCENT = Decimal(10)


@dataclass(frozen=True)
class Dose:
    """A drawn unit dose."""

    id: str
    order_id: str
    batch_id: str
    code: str
    drawn_at: dt.datetime
    calibration_at: dt.datetime
    volume: Volume
    assayed: Activity
    drawn_by: str
    calibrator_id: str | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.DOSE)
        expect(self.order_id, Kind.ORDER)
        expect(self.batch_id, Kind.BATCH)
        object.__setattr__(self, "code", formula(self.code).code)
        if self.volume.is_zero():
            raise ValidationError("a syringe with nothing in it is not a dose", id=self.id)
        if self.assayed.is_zero():
            raise ValidationError("a dose has to assay above zero", id=self.id)
        if self.calibration_at < self.drawn_at:
            raise ValidationError(
                "that dose is calibrated for a moment before it was drawn",
                id=self.id,
                drawn_at=self.drawn_at.isoformat(),
                calibration_at=self.calibration_at.isoformat(),
            )
        if not self.drawn_by.strip():
            raise ValidationError("a dose is signed by whoever drew it", id=self.id)
        if self.calibrator_id is not None:
            expect(self.calibrator_id, Kind.INSTRUMENT)

    @property
    def formula(self) -> Formula:
        return formula(self.code)

    def activity_at(self, moment: dt.datetime) -> Activity:
        """What the syringe holds at a moment, decayed from the assay."""
        if moment < self.drawn_at:
            raise ValidationError(
                "a dose has no activity before it was drawn",
                id=self.id,
                moment=moment.isoformat(),
            )
        return decay_between(self.assayed, nuclide(self.formula.nuclide), self.drawn_at, moment)

    @property
    def at_calibration(self) -> Activity:
        """What the syringe will read when the department injects it."""
        return self.activity_at(self.calibration_at)

    def variance_from(self, ordered: Activity) -> Decimal:
        """How far off the order this dose is, as a signed percentage."""
        if ordered.is_zero():
            raise ValidationError("a dose cannot be compared against no order", id=self.id)
        difference = self.at_calibration.uci - ordered.uci
        share = difference / ordered.uci * Decimal(100)
        return share.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    def within_tolerance(self, ordered: Activity, tolerance: Decimal = TOLERANCE_PERCENT) -> bool:
        return abs(self.variance_from(ordered)) <= tolerance

    def hours_held(self) -> Decimal:
        """How long the syringe sits between being drawn and being wanted."""
        from molycow.clock import hours_between

        return hours_between(self.drawn_at, self.calibration_at)

    def label(self, ordered: Activity, tz: ZoneInfo) -> str:
        """The line that goes on the syringe shield.

        The clock time is local, and the zone has to be passed in. A dose read
        back out of the book carries its calibration time in utc, so a label
        built off the stored moment alone comes out hours wrong and looks
        perfectly reasonable while it does it.
        """
        clock = self.calibration_at.astimezone(tz).strftime("%H%M")
        return (
            f"{self.id} {self.formula.nuclide} {self.formula.name} "
            f"{ordered.format('mci', 1)} at {clock}"
        )


@dataclass(frozen=True)
class DoseReturn:
    """A syringe the hospital sent back, and why."""

    dose_id: str
    returned_at: dt.datetime
    reason: str
    received_by: str
    container_id: str | None = None

    def __post_init__(self) -> None:
        expect(self.dose_id, Kind.DOSE)
        if not self.reason.strip():
            raise ValidationError("a return says why", dose=self.dose_id)
        if not self.received_by.strip():
            raise ValidationError("a return is signed for", dose=self.dose_id)
        if self.container_id is not None:
            expect(self.container_id, Kind.CONTAINER)
