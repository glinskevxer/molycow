"""The pharmacy's own licence, and the ceilings it puts on the building.

A materials licence names each nuclide the pharmacy may hold and the most it
may have on the premises at any one moment. The limit is on what is here now,
not on what was used over the week, which is why it can only ever be answered
by decaying everything in the building to the same moment and adding it up.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError
from molycow.nuclides import nuclide
from molycow.units import Activity


@dataclass(frozen=True)
class PossessionLimit:
    """The most of one nuclide the licence allows on the premises."""

    symbol: str
    limit: Activity
    note: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", nuclide(self.symbol).symbol)
        if self.limit.is_zero():
            raise ValidationError("a limit of nothing is not a limit", symbol=self.symbol)

    def allows(self, holding: Activity) -> bool:
        return holding <= self.limit

    def headroom(self, holding: Activity) -> Activity:
        """What is left under the limit, which is zero once it is reached."""
        if holding >= self.limit:
            return Activity.zero()
        return self.limit - holding

    def share_used(self, holding: Activity) -> Decimal:
        """How much of the licence is in use, as a fraction."""
        return holding.ratio_to(self.limit)

    def format(self) -> str:
        return f"{self.symbol} {self.limit.format('ci', 1)}"
