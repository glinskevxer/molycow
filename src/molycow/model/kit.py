"""Cold kits on the shelf, and the batches compounded out of them.

A kit lot is a box of identical cold vials with the maker's lot number on it.
A batch is one of those vials after eluate has gone into it, and from that
moment it has its own activity, its own volume and its own short life.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.decay import decay_between
from molycow.errors import ValidationError
from molycow.formulary import Formula, formula
from molycow.ids import Kind, expect
from molycow.nuclides import nuclide
from molycow.units import Activity, Concentration, Volume


@dataclass(frozen=True)
class KitLot:
    """A box of cold kits, as delivered."""

    id: str
    code: str
    maker: str
    lot: str
    received_on: dt.date
    expires_on: dt.date
    vials: int
    recalled_at: dt.datetime | None = None
    recall_reason: str | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.KIT_LOT)
        object.__setattr__(self, "code", formula(self.code).code)
        if not self.lot.strip():
            raise ValidationError("a kit lot needs the maker's lot number", id=self.id)
        if self.vials < 1:
            raise ValidationError("a kit lot with no vials in it is not a lot", id=self.id)
        if self.expires_on < self.received_on:
            raise ValidationError("that kit lot expired before it arrived", id=self.id)

    @property
    def formula(self) -> Formula:
        return formula(self.code)

    @property
    def is_recalled(self) -> bool:
        return self.recalled_at is not None

    def is_in_date(self, day: dt.date) -> bool:
        if self.is_recalled:
            return False
        return self.received_on <= day <= self.expires_on

    def recalled(self, at: dt.datetime, reason: str) -> KitLot:
        """The same lot pulled off the shelf, which only happens once."""
        if self.is_recalled:
            raise ValidationError("that lot has already been recalled", id=self.id)
        if not reason.strip():
            raise ValidationError("a recall says why", id=self.id)
        return KitLot(
            id=self.id,
            code=self.code,
            maker=self.maker,
            lot=self.lot,
            received_on=self.received_on,
            expires_on=self.expires_on,
            vials=self.vials,
            recalled_at=at,
            recall_reason=reason,
        )

    def days_left(self, day: dt.date) -> int:
        return (self.expires_on - day).days


@dataclass(frozen=True)
class Batch:
    """One compounded vial, from the moment the eluate went in."""

    id: str
    kit_lot_id: str
    elution_id: str
    code: str
    made_at: dt.datetime
    activity: Activity
    volume: Volume
    eluate_volume: Volume
    made_by: str
    rcp: Decimal | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.BATCH)
        expect(self.kit_lot_id, Kind.KIT_LOT)
        expect(self.elution_id, Kind.ELUTION)
        object.__setattr__(self, "code", formula(self.code).code)
        if not self.made_by.strip():
            raise ValidationError("a batch is signed by whoever compounded it", id=self.id)
        if self.eluate_volume.is_zero():
            raise ValidationError("a batch with no eluate in it has no activity", id=self.id)
        if self.eluate_volume > self.volume:
            raise ValidationError(
                "more eluate went in than the vial holds",
                id=self.id,
                eluate=str(self.eluate_volume),
                volume=str(self.volume),
            )
        self.formula.check(self.activity, self.volume)
        if self.rcp is not None and not (Decimal(0) <= self.rcp <= Decimal(100)):
            raise ValidationError("a purity reading is a percentage", id=self.id, rcp=str(self.rcp))

    @property
    def formula(self) -> Formula:
        return formula(self.code)

    @property
    def saline(self) -> Volume:
        """The saline added to bring the vial up to its made volume."""
        return self.volume - self.eluate_volume

    @property
    def expires_at(self) -> dt.datetime:
        return self.made_at + dt.timedelta(hours=float(self.formula.shelf_hours))

    @property
    def concentration(self) -> Concentration:
        return Concentration.of(self.activity, self.volume)

    def activity_at(self, moment: dt.datetime) -> Activity:
        """What the vial holds at a moment, decayed from the prep."""
        if moment < self.made_at:
            raise ValidationError(
                "a batch has no activity before it was made",
                id=self.id,
                moment=moment.isoformat(),
            )
        return decay_between(self.activity, nuclide(self.formula.nuclide), self.made_at, moment)

    def concentration_at(self, moment: dt.datetime) -> Concentration:
        return Concentration.of(self.activity_at(moment), self.volume)

    def is_in_date_at(self, moment: dt.datetime) -> bool:
        return self.made_at <= moment <= self.expires_at

    @property
    def is_tested(self) -> bool:
        return self.rcp is not None

    @property
    def is_pure_enough(self) -> bool:
        return self.rcp is not None and self.rcp >= self.formula.rcp_floor

    def with_purity(self, rcp: Decimal) -> Batch:
        """The same batch with its chromatography reading on it."""
        return Batch(
            id=self.id,
            kit_lot_id=self.kit_lot_id,
            elution_id=self.elution_id,
            code=self.code,
            made_at=self.made_at,
            activity=self.activity,
            volume=self.volume,
            eluate_volume=self.eluate_volume,
            made_by=self.made_by,
            rcp=rcp,
        )

    def hold_reason(self, moment: dt.datetime) -> str | None:
        """Why nothing may be drawn from this batch, or nothing."""
        if not self.is_tested:
            return "no purity reading yet"
        if not self.is_pure_enough:
            return "purity under the floor for this kit"
        if moment > self.expires_at:
            return "past its expiry"
        if moment < self.made_at:
            return "not made yet"
        return None
