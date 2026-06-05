"""What the film badges read, and the yearly limits they are read against.

Everybody who works in the hot lab wears two badges: one on the collar for the
whole body and one on the finger for the hands, because a technologist's hands
take an order of magnitude more than the rest of them. The limits are yearly,
so a quarter that looks small is only small until it is added to the three
before it.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError

DEEP_LIMIT_MREM = Decimal(5000)
EXTREMITY_LIMIT_MREM = Decimal(50000)

INVESTIGATION_SHARE = Decimal("0.10")

PERIOD = re.compile(r"^(\d{4})Q([1-4])$")


@dataclass(frozen=True)
class Badge:
    """One badge period for one person."""

    person: str
    period: str
    deep_mrem: Decimal
    extremity_mrem: Decimal
    read_on: dt.date

    def __post_init__(self) -> None:
        if not self.person.strip():
            raise ValidationError("a badge belongs to somebody")
        if PERIOD.match(self.period) is None:
            raise ValidationError("a badge period reads like '2025Q2'", period=self.period)
        for name, value in (("deep", self.deep_mrem), ("extremity", self.extremity_mrem)):
            if value < 0:
                raise ValidationError("a badge cannot read below zero", part=name)

    @property
    def year(self) -> int:
        match = PERIOD.match(self.period)
        assert match is not None
        return int(match.group(1))

    @property
    def quarter(self) -> int:
        match = PERIOD.match(self.period)
        assert match is not None
        return int(match.group(2))

    @property
    def over_investigation_level(self) -> bool:
        """A quarter over a tenth of the yearly limit is looked into."""
        return self.deep_mrem > DEEP_LIMIT_MREM * INVESTIGATION_SHARE

    def line(self) -> str:
        """The line the dosimetry report prints."""
        flag = "  investigate" if self.over_investigation_level else ""
        return (
            f"{self.period}  {self.person:16} deep {self.deep_mrem:>7} mrem  "
            f"extremity {self.extremity_mrem:>7} mrem{flag}"
        )


def quarter_of(day: dt.date) -> str:
    """The badge period a day falls in."""
    return f"{day.year}Q{(day.month - 1) // 3 + 1}"


@dataclass(frozen=True)
class YearToDate:
    """One person's badges for a year, added up."""

    person: str
    year: int
    badges: tuple[Badge, ...]

    @property
    def deep(self) -> Decimal:
        return sum((one.deep_mrem for one in self.badges), Decimal(0))

    @property
    def extremity(self) -> Decimal:
        return sum((one.extremity_mrem for one in self.badges), Decimal(0))

    @property
    def over_limit(self) -> bool:
        return self.deep > DEEP_LIMIT_MREM or self.extremity > EXTREMITY_LIMIT_MREM

    def share_used(self) -> Decimal:
        """How much of the yearly whole body limit has gone."""
        return (self.deep / DEEP_LIMIT_MREM * Decimal(100)).quantize(Decimal("0.1"))

    def line(self) -> str:
        """The line the yearly summary prints."""
        flag = "  OVER THE LIMIT" if self.over_limit else ""
        return (
            f"{self.year}  {self.person:16} deep {self.deep:>7} mrem "
            f"({self.share_used()}% of the year)  extremity {self.extremity:>7} mrem{flag}"
        )
