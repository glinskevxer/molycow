"""Reading and writing the decay in storage containers."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from molycow.errors import NotFoundError
from molycow.ids import Kind, make, next_serial
from molycow.model.waste import Container, ContainerKind, WasteItem
from molycow.store.book import Book
from molycow.store.rows import (
    activity_in,
    activity_out,
    decimal_in,
    decimal_out,
    maybe_moment_in,
    maybe_text_in,
    moment_in,
    moment_out,
    text_in,
)


class ContainerRepository:
    """The drums in the waste store."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, container: Container) -> Container:
        with self._book.atomic():
            self._book.execute(
                """
                INSERT INTO container (id, kind, opened_at, closed_at, disposed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    container.id,
                    container.kind.value,
                    moment_out(container.opened_at),
                    None if container.closed_at is None else moment_out(container.closed_at),
                    None if container.disposed_at is None else moment_out(container.disposed_at),
                ),
            )
            self._write_items(container)
        return container

    def _write_items(self, container: Container) -> None:
        self._book.execute_many(
            """
            INSERT INTO waste_item (container_id, symbol, activity, added_at, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    container.id,
                    item.symbol,
                    activity_out(item.activity),
                    moment_out(item.added_at),
                    item.source,
                )
                for item in container.items
            ],
        )

    def find(self, container_id: str) -> Container | None:
        row = self._book.one("SELECT * FROM container WHERE id = ?", (container_id,))
        if row is None:
            return None
        items = self._book.all(
            "SELECT * FROM waste_item WHERE container_id = ? ORDER BY added_at, source",
            (container_id,),
        )
        return Container(
            id=text_in(row, "id"),
            kind=ContainerKind(text_in(row, "kind")),
            opened_at=moment_in(row["opened_at"], "opened_at"),
            items=tuple(
                WasteItem(
                    symbol=text_in(one, "symbol"),
                    activity=activity_in(one["activity"], "activity"),
                    added_at=moment_in(one["added_at"], "added_at"),
                    source=text_in(one, "source"),
                )
                for one in items
            ),
            closed_at=maybe_moment_in(row["closed_at"], "closed_at"),
            disposed_at=maybe_moment_in(row["disposed_at"], "disposed_at"),
        )

    def get(self, container_id: str) -> Container:
        found = self.find(container_id)
        if found is None:
            raise NotFoundError("no such container", id=container_id)
        return found

    def all(self) -> list[Container]:
        rows = self._book.all("SELECT id FROM container ORDER BY opened_at, id")
        return [self.get(str(row["id"])) for row in rows]

    def open_containers(self, kind: ContainerKind | None = None) -> list[Container]:
        found = [one for one in self.all() if not one.is_closed]
        if kind is not None:
            found = [one for one in found if one.kind is kind]
        return found

    def in_storage(self) -> list[Container]:
        """Closed containers that have not been disposed of."""
        return [one for one in self.all() if one.is_closed and not one.is_disposed]

    def add_item(self, container_id: str, item: WasteItem) -> Container:
        container = self.get(container_id).with_item(item)
        self._book.execute(
            """
            INSERT INTO waste_item (container_id, symbol, activity, added_at, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                container_id,
                item.symbol,
                activity_out(item.activity),
                moment_out(item.added_at),
                item.source,
            ),
        )
        return container

    def close(self, container_id: str, at: dt.datetime) -> Container:
        closed = self.get(container_id).closed(at)
        self._book.execute(
            "UPDATE container SET closed_at = ? WHERE id = ?", (moment_out(at), container_id)
        )
        return closed

    def dispose(
        self, container_id: str, at: dt.datetime, disposed_by: str, survey_mrem: Decimal
    ) -> Container:
        self._book.execute(
            """
            UPDATE container SET disposed_at = ?, disposed_by = ?, survey_mrem = ?
            WHERE id = ?
            """,
            (moment_out(at), disposed_by, decimal_out(survey_mrem), container_id),
        )
        return self.get(container_id)

    def disposal_survey(self, container_id: str) -> Decimal | None:
        row = self._book.one("SELECT survey_mrem FROM container WHERE id = ?", (container_id,))
        if row is None or row["survey_mrem"] is None:
            return None
        return decimal_in(row["survey_mrem"], "survey_mrem")

    def disposed_by(self, container_id: str) -> str | None:
        row = self._book.one("SELECT disposed_by FROM container WHERE id = ?", (container_id,))
        return None if row is None else maybe_text_in(row, "disposed_by")

    def next_id(self) -> str:
        issued = [str(row["id"]) for row in self._book.all("SELECT id FROM container")]
        return make(Kind.CONTAINER, next_serial(issued, Kind.CONTAINER))
