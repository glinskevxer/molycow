"""Loading the van, sending it out, and reading what came back.

A box goes on the run that calls at its customer. The van has a limit of its
own, which is the sum of the transport indexes it is carrying, and it is
checked before the box goes on rather than at the kerb.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import RuleError
from molycow.model.route import VAN_INDEX_LIMIT, Route, Run
from molycow.model.shipment import Shipment
from molycow.store.book import Book
from molycow.store.routes import RouteRepository, RunRepository
from molycow.store.shipments import ShipmentRepository


@dataclass(frozen=True)
class Load:
    """What one run is carrying."""

    route: Route
    run: Run
    shipments: tuple[Shipment, ...]

    @property
    def index(self) -> Decimal:
        return sum((one.transport_index for one in self.shipments), Decimal(0)).quantize(
            Decimal("0.1")
        )

    @property
    def stops_with_boxes(self) -> list[str]:
        """The stops that have something for them, in the order the van calls."""
        waiting = {one.customer_id for one in self.shipments}
        return [stop for stop in self.route.stops if stop in waiting]

    def undelivered(self) -> list[Shipment]:
        return [one for one in self.shipments if not one.is_delivered]


class RouteService:
    """The dock, from the van's side."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._routes = RouteRepository(book)
        self._runs = RunRepository(book)
        self._shipments = ShipmentRepository(book)

    def open_run(self, route_id: str, day: dt.date, driver: str) -> Run:
        self._routes.get(route_id)
        return self._runs.add(Run(route_id, day, driver))

    def load(self, route_id: str, day: dt.date, shipment_id: str) -> Load:
        """Put a box on a run, if the run is the right one and has room."""
        route = self._routes.get(route_id)
        run = self._runs.get(route_id, day)
        shipment = self._shipments.get(shipment_id)
        if run.has_left:
            raise RuleError("run-gone", "that run has already left", route=route_id)
        if not route.calls_at(shipment.customer_id):
            raise RuleError(
                "run-stop",
                "that run does not call at that customer",
                route=route_id,
                customer=shipment.customer_id,
            )
        carried = self._runs.run_carrying(shipment_id)
        if carried is not None:
            raise RuleError("run-loaded", "that box is already on a run", shipment=shipment_id)
        loaded = self.load_of(route_id, day)
        if loaded.index + shipment.transport_index > VAN_INDEX_LIMIT:
            raise RuleError(
                "van-index",
                "that box would put the van over its transport index",
                route=route_id,
                index=str(loaded.index + shipment.transport_index),
            )
        self._runs.load(route_id, day, shipment_id)
        return self.load_of(route_id, day)

    def load_of(self, route_id: str, day: dt.date) -> Load:
        route = self._routes.get(route_id)
        run = self._runs.get(route_id, day)
        boxes = [self._shipments.get(one) for one in self._runs.shipments_on(route_id, day)]
        return Load(route, run, tuple(boxes))

    def depart(self, route_id: str, day: dt.date, at: dt.datetime) -> Run:
        """Send the van out, which an empty one does not get to do."""
        load = self.load_of(route_id, day)
        if not load.shipments:
            raise RuleError("run-empty", "there is nothing on that run", route=route_id)
        return self._runs.save(load.run.leaving(at))

    def deliver(
        self, route_id: str, day: dt.date, shipment_id: str, at: dt.datetime, received_by: str
    ) -> Shipment:
        """Sign a box over at a stop."""
        run = self._runs.get(route_id, day)
        if not run.has_left:
            raise RuleError("run-here", "that run has not left yet", route=route_id)
        carried = self._runs.run_carrying(shipment_id)
        if carried is None or carried[0] != route_id or carried[1] != day:
            raise RuleError(
                "run-not-carrying",
                "that box is not on that run",
                route=route_id,
                shipment=shipment_id,
            )
        return self._shipments.sign_for(shipment_id, at, received_by)

    def arrive_back(self, route_id: str, day: dt.date, at: dt.datetime) -> Run:
        run = self._runs.get(route_id, day)
        return self._runs.save(run.back(at))

    def waiting_for(self, route_id: str) -> list[Shipment]:
        """Boxes for this route's stops that are not on any run yet."""
        route = self._routes.get(route_id)
        waiting = []
        for shipment in self._shipments.undelivered():
            if not route.calls_at(shipment.customer_id):
                continue
            if self._runs.run_carrying(shipment.id) is not None:
                continue
            waiting.append(shipment)
        return waiting

    def runs_on(self, day: dt.date) -> list[Load]:
        return [self.load_of(run.route_id, day) for run in self._runs.on_day(day)]
