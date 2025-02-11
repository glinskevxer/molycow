"""The identifiers written on labels, and the rules for reading them back.

Two shapes are in use. Things the pharmacy numbers once and keeps for years
carry a flat serial: ``CU-0142``. Things it numbers again every morning carry
the day they belong to: ``EL-250408-03``, the third elution on the eighth of
April. The day in the middle is what lets a technologist read a syringe label
across the room and know whether it is today's.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from enum import Enum

from molycow.errors import ValidationError


class Kind(Enum):
    """Everything the pharmacy puts a number on."""

    CUSTOMER = "CU"
    AUTHORIZED_USER = "AU"
    INSTRUMENT = "IC"
    GENERATOR = "GEN"
    KIT_LOT = "KL"
    CONTAINER = "WC"
    ROUTE = "RT"
    ELUTION = "EL"
    BATCH = "B"
    DOSE = "DS"
    ORDER = "ORD"
    SURVEY = "SV"
    SHIPMENT = "SH"

    @property
    def is_daily(self) -> bool:
        """Whether the number restarts every morning."""
        return self in _DAILY


_DAILY = frozenset({Kind.ELUTION, Kind.BATCH, Kind.DOSE, Kind.ORDER, Kind.SURVEY, Kind.SHIPMENT})

_FLAT = re.compile(r"^(?P<prefix>[A-Z]{1,3})-(?P<serial>\d{3,6})$")
_DATED = re.compile(r"^(?P<prefix>[A-Z]{1,3})-(?P<day>\d{6})-(?P<serial>\d{2,3})$")

_BY_PREFIX = {kind.value: kind for kind in Kind}


@dataclass(frozen=True)
class Identifier:
    """A parsed label number."""

    kind: Kind
    serial: int
    day: dt.date | None = None

    def __str__(self) -> str:
        if self.day is None:
            return f"{self.kind.value}-{self.serial:04d}"
        return f"{self.kind.value}-{self.day:%y%m%d}-{self.serial:02d}"


def normalise(text: str) -> str:
    """Upper case, trimmed, and with the spaces people leave in taken out."""
    return text.strip().replace(" ", "").upper()


def parse(text: str) -> Identifier:
    """Read a label number back into its parts."""
    cleaned = normalise(text)
    dated = _DATED.match(cleaned)
    if dated is not None:
        kind = _kind_for(dated.group("prefix"), cleaned)
        if not kind.is_daily:
            raise ValidationError("that number does not carry a day", id=cleaned)
        return Identifier(kind, int(dated.group("serial")), _day_from(dated.group("day"), cleaned))
    flat = _FLAT.match(cleaned)
    if flat is not None:
        kind = _kind_for(flat.group("prefix"), cleaned)
        if kind.is_daily:
            raise ValidationError("that number is missing its day", id=cleaned)
        return Identifier(kind, int(flat.group("serial")))
    raise ValidationError("that is not a label number this pharmacy issues", id=cleaned)


def _kind_for(prefix: str, cleaned: str) -> Kind:
    kind = _BY_PREFIX.get(prefix)
    if kind is None:
        raise ValidationError("unknown label prefix", prefix=prefix, id=cleaned)
    return kind


def _day_from(digits: str, cleaned: str) -> dt.date:
    try:
        return dt.datetime.strptime(digits, "%y%m%d").date()  # noqa: DTZ007
    except ValueError:
        raise ValidationError("that number carries a day that is not a day", id=cleaned) from None


def make(kind: Kind, serial: int, day: dt.date | None = None) -> str:
    """Build the label number for a new record."""
    if serial < 1:
        raise ValidationError("a serial starts at one", serial=serial)
    if kind.is_daily:
        if day is None:
            raise ValidationError("this number needs the day it belongs to", kind=kind.value)
        if serial > 999:
            raise ValidationError(
                "more than 999 in one day, the serial has run out", kind=kind.value
            )
        return str(Identifier(kind, serial, day))
    if day is not None:
        raise ValidationError("this number does not carry a day", kind=kind.value)
    if serial > 999999:
        raise ValidationError("the serial has run out", kind=kind.value)
    return str(Identifier(kind, serial))


def expect(text: str, kind: Kind) -> Identifier:
    """Parse, and refuse anything that is not the kind of number wanted here."""
    found = parse(text)
    if found.kind is not kind:
        raise ValidationError(
            "that is the wrong kind of number here",
            id=normalise(text),
            wanted=kind.value,
            got=found.kind.value,
        )
    return found


def next_serial(existing: list[str], kind: Kind, day: dt.date | None = None) -> int:
    """The next serial for a kind, given what has been issued already."""
    used = []
    for text in existing:
        found = parse(text)
        if found.kind is not kind or found.day != day:
            continue
        used.append(found.serial)
    return max(used, default=0) + 1
