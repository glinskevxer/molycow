"""Who the pharmacy is allowed to ship to.

A dose leaves the building against a customer's radioactive materials licence
and an authorized user named on it. Both are on file here, and both can end,
because a physician moves and a licence lapses.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from enum import Enum

from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.nuclides import Use, fold_symbol, is_known, nuclide

LICENCE = re.compile(r"^\d{2}-\d{5}-\d{2}$")

ZONES = ("north", "south", "river", "county", "metro")


class CustomerKind(Enum):
    """What sort of place is receiving the dose."""

    HOSPITAL = "hospital"
    CLINIC = "clinic"
    IMAGING = "imaging"
    RESEARCH = "research"

    @property
    def takes_therapy(self) -> bool:
        """Whether this sort of place may receive a therapeutic dose."""
        return self in {CustomerKind.HOSPITAL, CustomerKind.RESEARCH}


def check_licence(text: str) -> str:
    """A materials licence reads like ``42-28931-01``."""
    cleaned = text.strip()
    if not LICENCE.match(cleaned):
        raise ValidationError("a licence number reads like '42-28931-01'", licence=text)
    return cleaned


def check_zone(text: str) -> str:
    cleaned = text.strip().lower()
    if cleaned not in ZONES:
        raise ValidationError("that is not a delivery zone", zone=text, zones=", ".join(ZONES))
    return cleaned


@dataclass(frozen=True)
class Customer:
    """A hospital, clinic or imaging centre on the route."""

    id: str
    name: str
    kind: CustomerKind
    licence: str
    street: str
    town: str
    zone: str
    opened_on: dt.date
    closed_on: dt.date | None = None

    def __post_init__(self) -> None:
        expect(self.id, Kind.CUSTOMER)
        if not self.name.strip():
            raise ValidationError("a customer needs a name", id=self.id)
        object.__setattr__(self, "licence", check_licence(self.licence))
        object.__setattr__(self, "zone", check_zone(self.zone))
        if self.closed_on is not None and self.closed_on < self.opened_on:
            raise ValidationError(
                "a customer cannot close before it opened",
                id=self.id,
                opened_on=self.opened_on.isoformat(),
                closed_on=self.closed_on.isoformat(),
            )

    def is_open_on(self, day: dt.date) -> bool:
        if day < self.opened_on:
            return False
        return self.closed_on is None or day <= self.closed_on

    def may_receive(self, symbol: str) -> bool:
        """Whether the sort of place this is may take that nuclide at all."""
        found = nuclide(symbol)
        if found.use is Use.THERAPEUTIC:
            return self.kind.takes_therapy
        return found.use is not Use.PARENT

    @property
    def address(self) -> str:
        return f"{self.street}, {self.town}"


@dataclass(frozen=True)
class AuthorizedUser:
    """A physician named on a customer's licence, and what they may order."""

    id: str
    customer_id: str
    name: str
    licence: str
    added_on: dt.date
    ended_on: dt.date | None = None
    nuclides: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        expect(self.id, Kind.AUTHORIZED_USER)
        expect(self.customer_id, Kind.CUSTOMER)
        if not self.name.strip():
            raise ValidationError("an authorized user needs a name", id=self.id)
        object.__setattr__(self, "licence", check_licence(self.licence))
        folded = set()
        for symbol in self.nuclides:
            if not is_known(symbol):
                raise ValidationError(
                    "that nuclide is not one this pharmacy handles",
                    id=self.id,
                    nuclide=symbol,
                )
            folded.add(fold_symbol(symbol))
        object.__setattr__(self, "nuclides", frozenset(folded))
        if self.ended_on is not None and self.ended_on < self.added_on:
            raise ValidationError("that user ended before they were added", id=self.id)

    def is_current_on(self, day: dt.date) -> bool:
        if day < self.added_on:
            return False
        return self.ended_on is None or day <= self.ended_on

    def may_order(self, symbol: str) -> bool:
        """Whether this user is named for that nuclide."""
        if not self.nuclides:
            return False
        return fold_symbol(symbol) in self.nuclides

    def with_nuclides(self, symbols: list[str]) -> AuthorizedUser:
        """A copy naming a different set of nuclides."""
        return AuthorizedUser(
            id=self.id,
            customer_id=self.customer_id,
            name=self.name,
            licence=self.licence,
            added_on=self.added_on,
            ended_on=self.ended_on,
            nuclides=frozenset(symbols),
        )
