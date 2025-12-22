"""What has to be true of a package before it leaves the dock.

Three numbers decide everything. The reading on the surface of the package,
the reading a metre away, and how much activity is inside compared against the
quantity that decides whether a Type A package is allowed to hold it.

The transport index is the metre reading rounded up, never down, because it is
a limit and rounding a limit down is how a package ends up in the wrong place
on a truck.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from enum import Enum

from molycow.errors import ValidationError
from molycow.nuclides import fold_symbol, nuclide
from molycow.units import Activity

SURFACE_LIMIT_MREM = Decimal(200)
METRE_LIMIT_MREM = Decimal(10)
CAB_LIMIT_MREM = Decimal(2)

WHITE_SURFACE_LIMIT = Decimal("0.5")
YELLOW_TWO_SURFACE_LIMIT = Decimal(50)
YELLOW_TWO_INDEX_LIMIT = Decimal(1)


class Label(Enum):
    """The label that goes on the outside of the package."""

    WHITE_I = "White-I"
    YELLOW_II = "Yellow-II"
    YELLOW_III = "Yellow-III"

    @property
    def needs_index_on_the_label(self) -> bool:
        return self is not Label.WHITE_I


A2_CURIES: dict[str, Decimal] = {
    "tc99m": Decimal("10.8"),
    "mo99": Decimal("16.2"),
    "f18": Decimal("16.2"),
    "i123": Decimal("8.1"),
    "i131": Decimal("0.7"),
    "in111": Decimal("8.1"),
    "ga67": Decimal("10.8"),
    "tl201": Decimal("10.8"),
    "lu177": Decimal("13.5"),
    "y90": Decimal("8.1"),
    "xe133": Decimal("27"),
    "sm153": Decimal("16.2"),
    "cs137": Decimal("16.2"),
    "co57": Decimal("16.2"),
    "ba133": Decimal("8.1"),
    "ge68": Decimal("10.8"),
    "ga68": Decimal("13.5"),
    "sr89": Decimal("16.2"),
}


def a2_quantity(symbol: str) -> Activity:
    """The A2 quantity for a nuclide, the ceiling for a Type A package."""
    found = nuclide(symbol)
    curies = A2_CURIES.get(fold_symbol(found.symbol))
    if curies is None:
        raise ValidationError("no A2 quantity on file for that nuclide", symbol=symbol)
    return Activity.of(curies, "ci")


def a2_fraction(symbol: str, activity: Activity) -> Decimal:
    """How much of the A2 quantity a package is carrying."""
    return activity.ratio_to(a2_quantity(symbol))


def fits_type_a(symbol: str, activity: Activity) -> bool:
    """Whether a Type A package may hold that much of a nuclide."""
    return a2_fraction(symbol, activity) <= Decimal(1)


def transport_index(metre_mrem: Decimal) -> Decimal:
    """The metre reading rounded up to a tenth, which is what the label carries."""
    if metre_mrem < 0:
        raise ValidationError("a reading cannot be negative", metre=str(metre_mrem))
    return metre_mrem.quantize(Decimal("0.1"), rounding=ROUND_CEILING)


def label_for(surface_mrem: Decimal, metre_mrem: Decimal) -> Label:
    """Which label the two readings put on the package."""
    if surface_mrem < 0:
        raise ValidationError("a reading cannot be negative", surface=str(surface_mrem))
    if surface_mrem > SURFACE_LIMIT_MREM:
        raise ValidationError(
            "that package is over the surface limit and cannot ship",
            surface=str(surface_mrem),
            limit=str(SURFACE_LIMIT_MREM),
        )
    index = transport_index(metre_mrem)
    if index > METRE_LIMIT_MREM:
        raise ValidationError(
            "that package is over the transport index limit and cannot ship",
            index=str(index),
            limit=str(METRE_LIMIT_MREM),
        )
    if surface_mrem <= WHITE_SURFACE_LIMIT and index == 0:
        return Label.WHITE_I
    if surface_mrem <= YELLOW_TWO_SURFACE_LIMIT and index <= YELLOW_TWO_INDEX_LIMIT:
        return Label.YELLOW_II
    return Label.YELLOW_III


def vehicle_index(indexes: list[Decimal]) -> Decimal:
    """The sum of the transport indexes on a truck, which has its own limit."""
    total = sum(indexes, Decimal(0))
    return total.quantize(Decimal("0.1"))


def fits_in_a_van(indexes: list[Decimal]) -> bool:
    """A van with no placards and no exclusive use carries up to fifty."""
    return vehicle_index(indexes) <= Decimal(50)
