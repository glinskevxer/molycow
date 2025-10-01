"""Reading and writing the courier routes and their daily runs."""

from __future__ import annotations

import datetime as dt

from molycow.clock import parse_clock
from molycow.errors import NotFoundError
from molycow.ids import Kind, make, next_serial
from molycow.model.route import Route, Run
from molycow.store.book import Book
from molycow.store.rows import date_in, date_out, maybe_moment_in, moment_out, text_in


class RouteRepository:
    """The standing runs."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, route: Route) -> Route:
        with self._book.atomic():
            self._book.execute(
                "INSERT INTO route (id, name, zone, leaves_at) VALUES (?, ?, ?, ?)",
                (route.id, route.name, route.zone, route.leaves_at.strftime("%H:%M")),
            )
            self._book.execute_many(
                "INSERT INTO route_stop (route_id, position, customer_id) VALUES (?, ?, ?)",
                [
                    (route.id, position, customer_id)
                    for position, customer_id in enumerate(route.stops, start=1)
                ],
            )
        return route

    def find(self, route_id: str) -> Route | None:
        row = self._book.one("SELECT * FROM route WHERE id = ?", (route_id,))
        if row is None:
            return None
        stops = self._book.all(
            "SELECT customer_id FROM route_stop WHERE route_id = ? ORDER BY position",
            (route_id,),
        )
        return Route(
            id=text_in(row, "id"),
            name=text_in(row, "name"),
            zone=text_in(row, "zone"),
            stops=tuple(str(one["customer_id"]) for one in stops),
            leaves_at=parse_clock(text_in(row, "leaves_at")),
        )

    def get(self, route_id: str) -> Route:
        found = self.find(route_id)
        if found is None:
            raise NotFoundError("no such route", id=route_id)
        return found

    def all(self) -> list[Route]:
        rows = self._book.all("SELECT id FROM route ORDER BY leaves_at, id")
        return [self.get(str(row["id"])) for row in rows]

    def for_zone(self, zone_name: str) -> list[Route]:
        return [one for one in self.all() if one.zone == zone_name]

    def calling_at(self, customer_id: str) -> list[Route]:
        return [one for one in self.all() if one.calls_at(customer_id)]

    def next_id(self) -> str:
        issued = [str(row["id"]) for row in self._book.all("SELECT id FROM route")]
        return make(Kind.ROUTE, next_serial(issued, Kind.ROUTE))


class RunRepository:
    """One day of a route, and what went on it."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, run: Run) -> Run:
        self._book.execute(
            """
            INSERT INTO route_run (route_id, day, driver, left_at, returned_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run.route_id,
                date_out(run.day),
                run.driver,
                None if run.left_at is None else moment_out(run.left_at),
                None if run.returned_at is None else moment_out(run.returned_at),
            ),
        )
        return run

    def find(self, route_id: str, day: dt.date) -> Run | None:
        row = self._book.one(
            "SELECT * FROM route_run WHERE route_id = ? AND day = ?",
            (route_id, date_out(day)),
        )
        if row is None:
            return None
        return Run(
            route_id=text_in(row, "route_id"),
            day=date_in(row["day"], "day"),
            driver=text_in(row, "driver"),
            left_at=maybe_moment_in(row["left_at"], "left_at"),
            returned_at=maybe_moment_in(row["returned_at"], "returned_at"),
        )

    def get(self, route_id: str, day: dt.date) -> Run:
        found = self.find(route_id, day)
        if found is None:
            raise NotFoundError("no such run", route=route_id, day=day.isoformat())
        return found

    def save(self, run: Run) -> Run:
        self._book.execute(
            "UPDATE route_run SET left_at = ?, returned_at = ? WHERE route_id = ? AND day = ?",
            (
                None if run.left_at is None else moment_out(run.left_at),
                None if run.returned_at is None else moment_out(run.returned_at),
                run.route_id,
                date_out(run.day),
            ),
        )
        return run

    def on_day(self, day: dt.date) -> list[Run]:
        rows = self._book.all(
            "SELECT route_id FROM route_run WHERE day = ? ORDER BY route_id", (date_out(day),)
        )
        return [self.get(str(row["route_id"]), day) for row in rows]

    def load(self, route_id: str, day: dt.date, shipment_id: str) -> None:
        """Put a box on a run."""
        self._book.execute(
            "INSERT INTO run_shipment (route_id, day, shipment_id) VALUES (?, ?, ?)",
            (route_id, date_out(day), shipment_id),
        )

    def shipments_on(self, route_id: str, day: dt.date) -> list[str]:
        rows = self._book.all(
            """
            SELECT shipment_id FROM run_shipment
            WHERE route_id = ? AND day = ? ORDER BY shipment_id
            """,
            (route_id, date_out(day)),
        )
        return [str(row["shipment_id"]) for row in rows]

    def run_carrying(self, shipment_id: str) -> tuple[str, dt.date] | None:
        row = self._book.one(
            "SELECT route_id, day FROM run_shipment WHERE shipment_id = ?", (shipment_id,)
        )
        if row is None:
            return None
        return str(row["route_id"]), date_in(row["day"], "day")
