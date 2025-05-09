"""Radiochemical purity, read off two chromatography strips.

A batch is not pure or impure, it is a mixture, and the two impurities are
found by two different strips. In the solvent system the free pertechnetate
runs with the front and everything else stays at the origin. In the saline
system the hydrolysed reduced technetium is the part that stays put. Neither
strip on its own says what the batch is; the purity is what is left after both
impurities are taken off.

Counts are what the well counter gives back. Background is subtracted before
anything is divided, because a low activity strip and a busy hot lab can put
enough background under a small number to move the answer by a percent.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from molycow.errors import ValidationError
from molycow.ids import Kind, expect

PERCENT = Decimal("0.1")


class System(Enum):
    """Which strip is being read."""

    SOLVENT = "solvent"
    SALINE = "saline"

    @property
    def impurity(self) -> str:
        if self is System.SOLVENT:
            return "free pertechnetate"
        return "hydrolysed reduced technetium"


@dataclass(frozen=True)
class Strip:
    """One strip, cut in two and counted."""

    system: System
    origin: int
    front: int
    background: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("origin", self.origin),
            ("front", self.front),
            ("background", self.background),
        ):
            if value < 0:
                raise ValidationError("a count cannot be negative", part=name, count=value)
        if self.net_total <= 0:
            raise ValidationError(
                "that strip counted nothing above background",
                system=self.system.value,
            )

    @property
    def net_origin(self) -> int:
        return max(self.origin - self.background, 0)

    @property
    def net_front(self) -> int:
        return max(self.front - self.background, 0)

    @property
    def net_total(self) -> int:
        return self.net_origin + self.net_front

    @property
    def impurity_percent(self) -> Decimal:
        """The share of the strip that is this system's impurity."""
        moving = self.net_front if self.system is System.SOLVENT else self.net_origin
        share = Decimal(moving) / Decimal(self.net_total) * Decimal(100)
        return share.quantize(PERCENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PurityTest:
    """Both strips for one batch, and what they say together."""

    batch_id: str
    tested_at: dt.datetime
    solvent: Strip
    saline: Strip
    tested_by: str

    def __post_init__(self) -> None:
        expect(self.batch_id, Kind.BATCH)
        if self.solvent.system is not System.SOLVENT:
            raise ValidationError("the solvent strip is in the wrong slot", batch=self.batch_id)
        if self.saline.system is not System.SALINE:
            raise ValidationError("the saline strip is in the wrong slot", batch=self.batch_id)
        if not self.tested_by.strip():
            raise ValidationError("a purity test is signed", batch=self.batch_id)

    @property
    def free_percent(self) -> Decimal:
        return self.solvent.impurity_percent

    @property
    def hydrolysed_percent(self) -> Decimal:
        return self.saline.impurity_percent

    @property
    def rcp(self) -> Decimal:
        """What is left once both impurities are taken off."""
        left = Decimal(100) - self.free_percent - self.hydrolysed_percent
        return max(left, Decimal(0)).quantize(PERCENT, rounding=ROUND_HALF_UP)

    def passes(self, floor: Decimal) -> bool:
        return self.rcp >= floor

    def worst_impurity(self) -> str:
        """Whichever impurity is the bigger of the two, for the log."""
        if self.hydrolysed_percent > self.free_percent:
            return System.SALINE.impurity
        return System.SOLVENT.impurity
