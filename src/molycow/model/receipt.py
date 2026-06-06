"""What has to be done to a package before it is opened.

A package of radioactive material is surveyed when it arrives, not when
somebody gets round to it: the readings on the outside and a wipe of the
outside, both within three hours of it being handed over. A package that fails
either one is not the pharmacy's to quietly open. The carrier and the regulator
have to be told.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError
from molycow.transport import Label, label_for, transport_index

WIPE_LIMIT_DPM = Decimal(2200)
SURFACE_LIMIT_MREM = Decimal(200)
INDEX_LIMIT = Decimal(10)

SURVEY_WITHIN_HOURS = Decimal(3)


@dataclass(frozen=True)
class PackageReceipt:
    """One package booked in at the dock."""

    reference: str
    supplier: str
    received_at: dt.datetime
    surface_mrem: Decimal
    metre_mrem: Decimal
    wipe_dpm: Decimal
    received_by: str

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValidationError("a receipt needs the carrier's reference")
        if not self.supplier.strip():
            raise ValidationError("a receipt says who sent it", reference=self.reference)
        if not self.received_by.strip():
            raise ValidationError("a receipt is signed", reference=self.reference)
        for name, value in (
            ("surface", self.surface_mrem),
            ("metre", self.metre_mrem),
            ("wipe", self.wipe_dpm),
        ):
            if value < 0:
                raise ValidationError(
                    "a reading cannot be negative", part=name, reference=self.reference
                )

    @property
    def transport_index(self) -> Decimal:
        return transport_index(self.metre_mrem)

    @property
    def label(self) -> Label | None:
        """The label the package should be carrying, if it is inside the limits."""
        try:
            return label_for(self.surface_mrem, self.metre_mrem)
        except ValidationError:
            return None

    @property
    def surface_passes(self) -> bool:
        return self.surface_mrem <= SURFACE_LIMIT_MREM

    @property
    def index_passes(self) -> bool:
        return self.transport_index <= INDEX_LIMIT

    @property
    def wipe_passes(self) -> bool:
        return self.wipe_dpm <= WIPE_LIMIT_DPM

    @property
    def passes(self) -> bool:
        return self.surface_passes and self.index_passes and self.wipe_passes

    def failure(self) -> str | None:
        """Why this package is not the pharmacy's to open."""
        if not self.surface_passes:
            return f"surface reading {self.surface_mrem} mrem/h over the limit"
        if not self.index_passes:
            return f"transport index {self.transport_index} over the limit"
        if not self.wipe_passes:
            return f"wipe {self.wipe_dpm} dpm over the limit"
        return None

    def line(self) -> str:
        """The line the receiving log prints."""
        verdict = self.failure() or "clean"
        label = "no label" if self.label is None else self.label.value
        return (
            f"{self.reference:14} {self.supplier:20} {self.received_at:%Y-%m-%d %H:%M}  "
            f"{label:10} TI {self.transport_index:>4}  {verdict}"
        )
