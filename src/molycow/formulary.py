"""The monographs the pharmacy compounds to.

A cold kit is a vial of freeze dried chemistry with no activity in it. It
becomes a radiopharmaceutical when eluate is added, and the package insert says
how much may go in, in what volume, how long it then lasts, and how pure it has
to be before it goes out. Those numbers are here, in one table, because half
the rules in this package are really a lookup against them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError
from molycow.units import Activity, Volume


@dataclass(frozen=True)
class Formula:
    """One monograph: what may be made, and the limits it is made inside."""

    code: str
    name: str
    nuclide: str
    min_activity: Activity
    max_activity: Activity
    min_volume: Volume
    max_volume: Volume
    shelf_hours: Decimal
    incubate_minutes: int
    boil: bool
    rcp_floor: Decimal
    dose_low: Activity
    dose_high: Activity
    refrigerate: bool = False

    def activity_fits(self, activity: Activity) -> bool:
        return self.min_activity <= activity <= self.max_activity

    def volume_fits(self, volume: Volume) -> bool:
        return self.min_volume <= volume <= self.max_volume

    def check(self, activity: Activity, volume: Volume) -> None:
        """Refuse a prep the insert does not allow, saying which limit it broke."""
        if not self.activity_fits(activity):
            raise ValidationError(
                "that activity is outside what the insert allows",
                kit=self.code,
                activity=str(activity),
                allowed=f"{self.min_activity} to {self.max_activity}",
            )
        if not self.volume_fits(volume):
            raise ValidationError(
                "that volume is outside what the insert allows",
                kit=self.code,
                volume=str(volume),
                allowed=f"{self.min_volume} to {self.max_volume}",
            )

    def dose_fits(self, activity: Activity) -> bool:
        """Whether an activity is a sensible adult unit dose of this product."""
        return self.dose_low <= activity <= self.dose_high

    def check_dose(self, activity: Activity) -> None:
        if not self.dose_fits(activity):
            raise ValidationError(
                "that is not an adult dose of this product",
                kit=self.code,
                activity=str(activity),
                usual=f"{self.dose_low} to {self.dose_high}",
            )

    @property
    def needs_incubation(self) -> bool:
        return self.incubate_minutes > 0

    def __str__(self) -> str:
        return f"{self.nuclide} {self.name}"


def _mci(value: object) -> Activity:
    return Activity.of(value, "mci")


def _ml(value: object) -> Volume:
    return Volume.of(value)


_TABLE: tuple[Formula, ...] = (
    Formula(
        code="MDP",
        name="medronate",
        nuclide="Tc-99m",
        min_activity=_mci(100),
        max_activity=_mci(400),
        min_volume=_ml(3),
        max_volume=_ml(10),
        shelf_hours=Decimal(6),
        incubate_minutes=0,
        boil=False,
        rcp_floor=Decimal(90),
        dose_low=_mci("15"),
        dose_high=_mci("30"),
    ),
    Formula(
        code="SESTA",
        name="sestamibi",
        nuclide="Tc-99m",
        min_activity=_mci(100),
        max_activity=_mci(150),
        min_volume=_ml(1),
        max_volume=_ml(3),
        shelf_hours=Decimal(6),
        incubate_minutes=10,
        boil=True,
        rcp_floor=Decimal(90),
        dose_low=_mci("8"),
        dose_high=_mci("35"),
    ),
    Formula(
        code="MAA",
        name="macroaggregated albumin",
        nuclide="Tc-99m",
        min_activity=_mci(20),
        max_activity=_mci(150),
        min_volume=_ml(2),
        max_volume=_ml(8),
        shelf_hours=Decimal(8),
        incubate_minutes=0,
        boil=False,
        rcp_floor=Decimal(90),
        refrigerate=True,
        dose_low=_mci("1"),
        dose_high=_mci("6"),
    ),
    Formula(
        code="MAG3",
        name="mertiatide",
        nuclide="Tc-99m",
        min_activity=_mci(20),
        max_activity=_mci(100),
        min_volume=_ml(4),
        max_volume=_ml(10),
        shelf_hours=Decimal(6),
        incubate_minutes=10,
        boil=True,
        rcp_floor=Decimal(90),
        dose_low=_mci("2"),
        dose_high=_mci("12"),
    ),
    Formula(
        code="SC",
        name="sulfur colloid",
        nuclide="Tc-99m",
        min_activity=_mci(10),
        max_activity=_mci(100),
        min_volume=_ml(1),
        max_volume=_ml(5),
        shelf_hours=Decimal(6),
        incubate_minutes=5,
        boil=True,
        rcp_floor=Decimal(92),
        dose_low=_mci("0.5"),
        dose_high=_mci("12"),
    ),
    Formula(
        code="PYP",
        name="pyrophosphate",
        nuclide="Tc-99m",
        min_activity=_mci(20),
        max_activity=_mci(150),
        min_volume=_ml(2),
        max_volume=_ml(10),
        shelf_hours=Decimal(6),
        incubate_minutes=0,
        boil=False,
        rcp_floor=Decimal(90),
        dose_low=_mci("10"),
        dose_high=_mci("25"),
    ),
    Formula(
        code="DTPA",
        name="pentetate",
        nuclide="Tc-99m",
        min_activity=_mci(20),
        max_activity=_mci(200),
        min_volume=_ml(2),
        max_volume=_ml(10),
        shelf_hours=Decimal(6),
        incubate_minutes=0,
        boil=False,
        rcp_floor=Decimal(90),
        dose_low=_mci("2"),
        dose_high=_mci("20"),
    ),
    Formula(
        code="MDPHDP",
        name="oxidronate",
        nuclide="Tc-99m",
        min_activity=_mci(100),
        max_activity=_mci(300),
        min_volume=_ml(3),
        max_volume=_ml(10),
        shelf_hours=Decimal(8),
        incubate_minutes=0,
        boil=False,
        rcp_floor=Decimal(90),
        dose_low=_mci("15"),
        dose_high=_mci("30"),
    ),
)

_BY_CODE = {one.code: one for one in _TABLE}


def formula(code: str) -> Formula:
    """Look up a monograph by the code on the kit box."""
    found = _BY_CODE.get(code.strip().upper())
    if found is None:
        raise ValidationError("this pharmacy does not compound that kit", kit=code)
    return found


def known() -> tuple[Formula, ...]:
    return _TABLE


def codes() -> tuple[str, ...]:
    return tuple(one.code for one in _TABLE)


def is_known(code: str) -> bool:
    return code.strip().upper() in _BY_CODE


def boiled() -> tuple[Formula, ...]:
    """The kits that go in the heating block."""
    return tuple(one for one in _TABLE if one.boil)
