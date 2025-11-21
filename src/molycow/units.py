"""Activity, volume and concentration, and the strings people write them as.

Activity is kept in microcuries because that is the number on the dose
calibrator in this pharmacy and rounding it once, on the way in, keeps every
later comparison exact. The becquerel conversion is exact by definition:
1 Ci is 3.7e10 Bq, so 1 uCi is 37000 Bq and nothing here has to approximate it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from molycow.errors import ValidationError

ACTIVITY_STEP = Decimal("0.001")
VOLUME_STEP = Decimal("0.001")

BQ_PER_UCI = Decimal("37000")

_ACTIVITY_UNITS: dict[str, Decimal] = {
    "bq": Decimal(1) / BQ_PER_UCI,
    "kbq": Decimal(1000) / BQ_PER_UCI,
    "mbq": Decimal(1000000) / BQ_PER_UCI,
    "gbq": Decimal(1000000000) / BQ_PER_UCI,
    "nci": Decimal("0.001"),
    "uci": Decimal(1),
    "mci": Decimal(1000),
    "ci": Decimal(1000000),
}

_UNIT_SPELLING = {
    "bq": "Bq",
    "kbq": "kBq",
    "mbq": "MBq",
    "gbq": "GBq",
    "nci": "nCi",
    "uci": "uCi",
    "mci": "mCi",
    "ci": "Ci",
}

_QUANTITY = re.compile(r"^\s*(?P<value>[-+]?[0-9]*\.?[0-9]+)\s*(?P<unit>[A-Za-zµμ]+)\s*$")


def _fold_unit(unit: str) -> str:
    return unit.replace("µ", "u").replace("μ", "u").lower()


def _as_decimal(value: object, what: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValidationError(f"{what} is not a number", value=value) from None
    raise ValidationError(f"{what} is not a number", value=repr(value))


@dataclass(frozen=True, order=True)
class Activity:
    """An amount of radioactivity, held in microcuries."""

    uci: Decimal

    def __post_init__(self) -> None:
        if self.uci < 0:
            raise ValidationError("activity cannot be negative", uci=str(self.uci))
        object.__setattr__(self, "uci", self.uci.quantize(ACTIVITY_STEP, rounding=ROUND_HALF_UP))

    @classmethod
    def zero(cls) -> Activity:
        return cls(Decimal(0))

    @classmethod
    def of(cls, value: object, unit: str) -> Activity:
        folded = _fold_unit(unit)
        factor = _ACTIVITY_UNITS.get(folded)
        if factor is None:
            raise ValidationError("unknown activity unit", unit=unit)
        return cls(_as_decimal(value, "activity") * factor)

    @classmethod
    def parse(cls, text: str) -> Activity:
        """Read ``25 mCi``, ``925MBq`` or ``300 uCi`` the way an order sheet writes it."""
        match = _QUANTITY.match(text)
        if match is None:
            raise ValidationError("activity should read like '25 mCi'", text=text)
        return cls.of(match.group("value"), match.group("unit"))

    @property
    def mci(self) -> Decimal:
        return (self.uci / Decimal(1000)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    @property
    def mbq(self) -> Decimal:
        return (self.uci * BQ_PER_UCI / Decimal(1000000)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

    @property
    def ci_value(self) -> Decimal:
        """The activity in curies, for the places that are written in curies."""
        return (self.uci / Decimal(1000000)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    @property
    def bq(self) -> Decimal:
        return self.uci * BQ_PER_UCI

    def is_zero(self) -> bool:
        return self.uci == 0

    def __add__(self, other: Activity) -> Activity:
        return Activity(self.uci + other.uci)

    def __sub__(self, other: Activity) -> Activity:
        if other.uci > self.uci:
            raise ValidationError(
                "activity cannot go below zero", have=str(self.uci), take=str(other.uci)
            )
        return Activity(self.uci - other.uci)

    def scaled(self, factor: object) -> Activity:
        ratio = _as_decimal(factor, "factor")
        if ratio < 0:
            raise ValidationError("cannot scale activity by a negative factor", factor=str(ratio))
        return Activity(self.uci * ratio)

    def ratio_to(self, other: Activity) -> Decimal:
        if other.is_zero():
            raise ValidationError("cannot take a ratio against zero activity")
        return self.uci / other.uci

    def format(self, unit: str = "mci", places: int = 3) -> str:
        folded = _fold_unit(unit)
        factor = _ACTIVITY_UNITS.get(folded)
        if factor is None:
            raise ValidationError("unknown activity unit", unit=unit)
        step = Decimal(1).scaleb(-places)
        value = (self.uci / factor).quantize(step, rounding=ROUND_HALF_UP)
        return f"{value} {_UNIT_SPELLING[folded]}"

    def __str__(self) -> str:
        return self.format()

    def __format__(self, spec: str) -> str:
        """Let an activity be padded in an f-string like the text it prints as."""
        return format(str(self), spec)


@dataclass(frozen=True, order=True)
class Volume:
    """A liquid volume in millilitres, kept to the microlitre."""

    ml: Decimal

    def __post_init__(self) -> None:
        if self.ml < 0:
            raise ValidationError("volume cannot be negative", ml=str(self.ml))
        object.__setattr__(self, "ml", self.ml.quantize(VOLUME_STEP, rounding=ROUND_HALF_UP))

    @classmethod
    def zero(cls) -> Volume:
        return cls(Decimal(0))

    @classmethod
    def of(cls, value: object) -> Volume:
        return cls(_as_decimal(value, "volume"))

    @classmethod
    def parse(cls, text: str) -> Volume:
        match = _QUANTITY.match(text)
        if match is None:
            return cls.of(text.strip())
        unit = _fold_unit(match.group("unit"))
        value = _as_decimal(match.group("value"), "volume")
        if unit in {"ml", "cc"}:
            return cls(value)
        if unit in {"ul", "mcl"}:
            return cls(value / Decimal(1000))
        raise ValidationError("unknown volume unit", unit=match.group("unit"))

    def is_zero(self) -> bool:
        return self.ml == 0

    def __add__(self, other: Volume) -> Volume:
        return Volume(self.ml + other.ml)

    def __sub__(self, other: Volume) -> Volume:
        if other.ml > self.ml:
            raise ValidationError(
                "volume cannot go below zero", have=str(self.ml), take=str(other.ml)
            )
        return Volume(self.ml - other.ml)

    def scaled(self, factor: object) -> Volume:
        ratio = _as_decimal(factor, "factor")
        if ratio < 0:
            raise ValidationError("cannot scale volume by a negative factor", factor=str(ratio))
        return Volume(self.ml * ratio)

    def __str__(self) -> str:
        return f"{self.ml} mL"

    def __format__(self, spec: str) -> str:
        return format(str(self), spec)


@dataclass(frozen=True)
class Concentration:
    """How much activity sits in a millilitre of a vial."""

    uci_per_ml: Decimal

    def __post_init__(self) -> None:
        if self.uci_per_ml <= 0:
            raise ValidationError("concentration has to be positive", value=str(self.uci_per_ml))

    @classmethod
    def of(cls, activity: Activity, volume: Volume) -> Concentration:
        if volume.is_zero():
            raise ValidationError("cannot take a concentration in zero volume")
        return cls(activity.uci / volume.ml)

    def volume_for(self, activity: Activity) -> Volume:
        """The volume that holds ``activity`` at this concentration."""
        return Volume(activity.uci / self.uci_per_ml)

    def activity_in(self, volume: Volume) -> Activity:
        return Activity(self.uci_per_ml * volume.ml)

    def format(self, unit: str = "mci", places: int = 3) -> str:
        return f"{Activity(self.uci_per_ml).format(unit, places)}/mL"

    def __str__(self) -> str:
        return self.format()
