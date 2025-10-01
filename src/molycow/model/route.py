"""The courier runs, and the stops on them.

A route is a standing thing: the north run leaves at half six and calls at the
same four hospitals in the same order every morning. A run is one day of it,
with a driver, a departure and, when the van comes back, a return.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.errors import ValidationError
from molycow.ids import Kind, expect
from molycow.model.register import check_zone

VAN_INDEX_LIMIT = Decimal(50)


@dataclass(frozen=True)
class Route:
    """A standing courier run."""

    id: str
    name: str
    zone: str
    stops: tuple[str, ...]
    leaves_at: dt.time

    def __post_init__(self) -> None:
        expect(self.id, Kind.ROUTE)
        if not self.name.strip():
            raise ValidationError("a route needs a name", id=self.id)
        object.__setattr__(self, "zone", check_zone(self.zone))
        if not self.stops:
            raise ValidationError("a route with no stops is not a route", id=self.id)
        for stop in self.stops:
            expect(stop, Kind.CUSTOMER)
        if len(set(self.stops)) != len(self.stops):
            raise ValidationError("a route calls at each stop once", id=self.id)

    def calls_at(self, customer_id: str) -> bool:
        return customer_id in self.stops

    def position_of(self, customer_id: str) -> int:
        """Where a stop falls on the run, counting from one."""
        if not self.calls_at(customer_id):
            raise ValidationError(
                "that customer is not on this route", route=self.id, customer=customer_id
            )
        return self.stops.index(customer_id) + 1

    @property
    def stop_count(self) -> int:
        return len(self.stops)


@dataclass(frozen=True)
class Run:
    """One day of a route."""

    route_id: str
    day: dt.date
    driver: str
    left_at: dt.datetime | None = None
    returned_at: dt.datetime | None = None

    def __post_init__(self) -> None:
        expect(self.route_id, Kind.ROUTE)
        if not self.driver.strip():
            raise ValidationError("a run needs a driver", route=self.route_id)
        if self.returned_at is not None and self.left_at is None:
            raise ValidationError("a run cannot come back before it left", route=self.route_id)
        if (
            self.left_at is not None
            and self.returned_at is not None
            and self.returned_at < self.left_at
        ):
            raise ValidationError("that run came back before it left", route=self.route_id)

    @property
    def has_left(self) -> bool:
        return self.left_at is not None

    @property
    def is_back(self) -> bool:
        return self.returned_at is not None

    def leaving(self, at: dt.datetime) -> Run:
        if self.has_left:
            raise ValidationError("that run has already left", route=self.route_id)
        return Run(self.route_id, self.day, self.driver, at, None)

    def back(self, at: dt.datetime) -> Run:
        if not self.has_left:
            raise ValidationError("that run has not left yet", route=self.route_id)
        if self.is_back:
            raise ValidationError("that run is already back", route=self.route_id)
        return Run(self.route_id, self.day, self.driver, self.left_at, at)
