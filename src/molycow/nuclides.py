"""The radionuclides this pharmacy handles, and their half lives.

Half lives are the values the pharmacy's own procedure manual quotes, kept as
decimal hours so the decay math never has to touch a float. A nuclide is
looked up by the symbol written on the vial: ``Tc-99m``, ``I-131``, ``F-18``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from molycow.errors import ValidationError

HOURS_PER_DAY = Decimal(24)
HOURS_PER_YEAR = Decimal("8766")


class Use(Enum):
    """What a nuclide is in the building for."""

    DIAGNOSTIC = "diagnostic"
    THERAPEUTIC = "therapeutic"
    PARENT = "parent"
    CHECK_SOURCE = "check source"


@dataclass(frozen=True)
class Nuclide:
    """One radionuclide, with the numbers the hot lab needs about it."""

    symbol: str
    element: str
    half_life_hours: Decimal
    use: Use
    principal_kev: Decimal | None = None
    parent: str | None = None

    @property
    def key(self) -> str:
        """The symbol folded the way a lookup folds it."""
        return fold_symbol(self.symbol)

    @property
    def half_life_days(self) -> Decimal:
        return self.half_life_hours / HOURS_PER_DAY

    @property
    def is_short_lived(self) -> bool:
        """Short enough that a dose is drawn and used the same shift."""
        return self.half_life_hours < Decimal(24)

    def __str__(self) -> str:
        return self.symbol


def fold_symbol(symbol: str) -> str:
    """``tc99m``, ``Tc 99m`` and ``TC-99M`` are all the same nuclide."""
    return symbol.replace("-", "").replace(" ", "").replace("_", "").lower()


_TABLE: tuple[Nuclide, ...] = (
    Nuclide("Mo-99", "molybdenum", Decimal("65.976"), Use.PARENT, Decimal("740")),
    Nuclide("Tc-99m", "technetium", Decimal("6.0067"), Use.DIAGNOSTIC, Decimal("140.5"), "Mo-99"),
    Nuclide("F-18", "fluorine", Decimal("1.82945"), Use.DIAGNOSTIC, Decimal("511")),
    Nuclide("Ga-68", "gallium", Decimal("1.12833"), Use.DIAGNOSTIC, Decimal("511"), "Ge-68"),
    Nuclide("Ge-68", "germanium", Decimal("6499.2"), Use.PARENT),
    Nuclide("I-123", "iodine", Decimal("13.2234"), Use.DIAGNOSTIC, Decimal("159")),
    Nuclide("I-131", "iodine", Decimal("192.605"), Use.THERAPEUTIC, Decimal("364.5")),
    Nuclide("In-111", "indium", Decimal("67.313"), Use.DIAGNOSTIC, Decimal("245")),
    Nuclide("Ga-67", "gallium", Decimal("78.281"), Use.DIAGNOSTIC, Decimal("93")),
    Nuclide("Tl-201", "thallium", Decimal("72.912"), Use.DIAGNOSTIC, Decimal("167")),
    Nuclide("Xe-133", "xenon", Decimal("125.832"), Use.DIAGNOSTIC, Decimal("81")),
    Nuclide("Lu-177", "lutetium", Decimal("159.528"), Use.THERAPEUTIC, Decimal("208")),
    Nuclide("Y-90", "yttrium", Decimal("64.053"), Use.THERAPEUTIC),
    Nuclide("Sm-153", "samarium", Decimal("46.284"), Use.THERAPEUTIC, Decimal("103")),
    Nuclide("Sr-89", "strontium", Decimal("1213.2"), Use.THERAPEUTIC),
    Nuclide("Cs-137", "caesium", Decimal("263652"), Use.CHECK_SOURCE, Decimal("661.7")),
    Nuclide("Co-57", "cobalt", Decimal("6521.76"), Use.CHECK_SOURCE, Decimal("122")),
    Nuclide("Ba-133", "barium", Decimal("92489.6"), Use.CHECK_SOURCE, Decimal("356")),
)

_BY_KEY: dict[str, Nuclide] = {n.key: n for n in _TABLE}


def nuclide(symbol: str) -> Nuclide:
    """Look one up by the symbol on the vial."""
    found = _BY_KEY.get(fold_symbol(symbol))
    if found is None:
        raise ValidationError("this pharmacy does not handle that nuclide", symbol=symbol)
    return found


def known() -> tuple[Nuclide, ...]:
    """Every nuclide in the table, in the order the manual lists them."""
    return _TABLE


def for_use(use: Use) -> tuple[Nuclide, ...]:
    """Every nuclide the table holds for one purpose."""
    return tuple(n for n in _TABLE if n.use is use)


def daughters_of(symbol: str) -> tuple[Nuclide, ...]:
    """Everything the table says grows in from this parent."""
    parent = nuclide(symbol)
    return tuple(n for n in _TABLE if n.parent is not None and fold_symbol(n.parent) == parent.key)


def is_known(symbol: str) -> bool:
    """Whether this pharmacy handles that nuclide."""
    return fold_symbol(symbol) in _BY_KEY
