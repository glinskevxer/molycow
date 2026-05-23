"""The fridge the cold kits live in, and the readings taken off it.

Some kits are stored between two and eight degrees, and a lot that has been
warm is a lot nobody can vouch for. A reading outside the range is an
excursion, and an excursion stays open until somebody has looked at it and
said what was done, which is the part that gets skipped on a busy afternoon.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError

LOWEST = Decimal(2)
HIGHEST = Decimal(8)


@dataclass(frozen=True)
class FridgeReading:
    """One reading off the fridge thermometer."""

    read_at: dt.datetime
    celsius: Decimal
    read_by: str
    reviewed_at: dt.datetime | None = None
    reviewed_by: str | None = None

    def __post_init__(self) -> None:
        if not self.read_by.strip():
            raise ValidationError("a reading says who took it")
        if self.celsius < Decimal(-40) or self.celsius > Decimal(60):
            raise ValidationError(
                "that is not a reading off a fridge thermometer",
                celsius=str(self.celsius),
            )
        if self.reviewed_at is not None and self.reviewed_at < self.read_at:
            raise ValidationError("that reading was reviewed before it was taken")
        if (self.reviewed_at is None) != (self.reviewed_by is None):
            raise ValidationError("a review has both a moment and a name, or neither")

    @property
    def in_range(self) -> bool:
        return LOWEST <= self.celsius <= HIGHEST

    @property
    def is_excursion(self) -> bool:
        return not self.in_range

    @property
    def is_reviewed(self) -> bool:
        return self.reviewed_at is not None

    @property
    def is_open(self) -> bool:
        """An excursion nobody has looked at yet."""
        return self.is_excursion and not self.is_reviewed

    def reviewed(self, at: dt.datetime, by: str) -> FridgeReading:
        """The same reading with somebody's name against it."""
        if not self.is_excursion:
            raise ValidationError("a reading in range does not need reviewing")
        if self.is_reviewed:
            raise ValidationError("that excursion has already been reviewed")
        return FridgeReading(self.read_at, self.celsius, self.read_by, at, by)

    def line(self) -> str:
        """The line the fridge log prints."""
        verdict = "in range"
        if self.is_open:
            verdict = "EXCURSION, not reviewed"
        elif self.is_excursion:
            verdict = f"excursion, reviewed by {self.reviewed_by}"
        return f"{self.read_at:%Y-%m-%d %H:%M}  {self.celsius:>5} C  {self.read_by:14} {verdict}"
