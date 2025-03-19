"""Reading and writing the customer register."""

from __future__ import annotations

import datetime as dt
import sqlite3

from molycow.errors import NotFoundError
from molycow.model.register import AuthorizedUser, Customer, CustomerKind
from molycow.store.book import Book
from molycow.store.rows import date_in, date_out, maybe_date_in, maybe_text_in, text_in


def customer_from(row: sqlite3.Row) -> Customer:
    return Customer(
        id=text_in(row, "id"),
        name=text_in(row, "name"),
        kind=CustomerKind(text_in(row, "kind")),
        licence=text_in(row, "licence"),
        street=text_in(row, "street"),
        town=text_in(row, "town"),
        zone=text_in(row, "zone"),
        opened_on=date_in(row["opened_on"], "opened_on"),
        closed_on=maybe_date_in(row["closed_on"], "closed_on"),
    )


class CustomerRepository:
    """The places the pharmacy ships to."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, customer: Customer) -> Customer:
        self._book.execute(
            """
            INSERT INTO customer
              (id, name, kind, licence, street, town, zone, opened_on, closed_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer.id,
                customer.name,
                customer.kind.value,
                customer.licence,
                customer.street,
                customer.town,
                customer.zone,
                date_out(customer.opened_on),
                date_out(customer.closed_on),
            ),
        )
        return customer

    def find(self, customer_id: str) -> Customer | None:
        row = self._book.one("SELECT * FROM customer WHERE id = ?", (customer_id,))
        return None if row is None else customer_from(row)

    def get(self, customer_id: str) -> Customer:
        found = self.find(customer_id)
        if found is None:
            raise NotFoundError("no such customer", id=customer_id)
        return found

    def by_name(self, name: str) -> Customer:
        row = self._book.one("SELECT * FROM customer WHERE name = ?", (name,))
        if row is None:
            raise NotFoundError("no customer by that name", name=name)
        return customer_from(row)

    def all(self, zone: str | None = None, open_on: dt.date | None = None) -> list[Customer]:
        rows = self._book.all("SELECT * FROM customer ORDER BY id")
        found = [customer_from(row) for row in rows]
        if zone is not None:
            found = [one for one in found if one.zone == zone]
        if open_on is not None:
            found = [one for one in found if one.is_open_on(open_on)]
        return found

    def close(self, customer_id: str, on: dt.date) -> Customer:
        """Mark a customer closed, which keeps every record that names it."""
        current = self.get(customer_id)
        closed = Customer(
            id=current.id,
            name=current.name,
            kind=current.kind,
            licence=current.licence,
            street=current.street,
            town=current.town,
            zone=current.zone,
            opened_on=current.opened_on,
            closed_on=on,
        )
        self._book.execute(
            "UPDATE customer SET closed_on = ? WHERE id = ?",
            (date_out(closed.closed_on), closed.id),
        )
        return closed

    def count(self) -> int:
        return int(self._book.value("SELECT count(*) FROM customer") or 0)


class AuthorizedUserRepository:
    """The physicians named on those licences."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def add(self, user: AuthorizedUser) -> AuthorizedUser:
        with self._book.atomic():
            self._book.execute(
                """
                INSERT INTO authorized_user
                  (id, customer_id, name, licence, added_on, ended_on)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.customer_id,
                    user.name,
                    user.licence,
                    date_out(user.added_on),
                    date_out(user.ended_on),
                ),
            )
            self._write_nuclides(user)
        return user

    def _write_nuclides(self, user: AuthorizedUser) -> None:
        self._book.execute("DELETE FROM authorized_nuclide WHERE user_id = ?", (user.id,))
        self._book.execute_many(
            "INSERT INTO authorized_nuclide (user_id, nuclide) VALUES (?, ?)",
            [(user.id, symbol) for symbol in sorted(user.nuclides)],
        )

    def _user_from(self, row: sqlite3.Row) -> AuthorizedUser:
        symbols = self._book.all(
            "SELECT nuclide FROM authorized_nuclide WHERE user_id = ? ORDER BY nuclide",
            (row["id"],),
        )
        return AuthorizedUser(
            id=text_in(row, "id"),
            customer_id=text_in(row, "customer_id"),
            name=text_in(row, "name"),
            licence=text_in(row, "licence"),
            added_on=date_in(row["added_on"], "added_on"),
            ended_on=maybe_date_in(row["ended_on"], "ended_on"),
            nuclides=frozenset(str(one["nuclide"]) for one in symbols),
        )

    def find(self, user_id: str) -> AuthorizedUser | None:
        row = self._book.one("SELECT * FROM authorized_user WHERE id = ?", (user_id,))
        return None if row is None else self._user_from(row)

    def get(self, user_id: str) -> AuthorizedUser:
        found = self.find(user_id)
        if found is None:
            raise NotFoundError("no such authorized user", id=user_id)
        return found

    def for_customer(self, customer_id: str, on: dt.date | None = None) -> list[AuthorizedUser]:
        rows = self._book.all(
            "SELECT * FROM authorized_user WHERE customer_id = ? ORDER BY id",
            (customer_id,),
        )
        found = [self._user_from(row) for row in rows]
        if on is not None:
            found = [one for one in found if one.is_current_on(on)]
        return found

    def set_nuclides(self, user_id: str, symbols: list[str]) -> AuthorizedUser:
        changed = self.get(user_id).with_nuclides(symbols)
        with self._book.atomic():
            self._write_nuclides(changed)
        return changed

    def end(self, user_id: str, on: dt.date) -> AuthorizedUser:
        current = self.get(user_id)
        ended = AuthorizedUser(
            id=current.id,
            customer_id=current.customer_id,
            name=current.name,
            licence=current.licence,
            added_on=current.added_on,
            ended_on=on,
            nuclides=current.nuclides,
        )
        self._book.execute(
            "UPDATE authorized_user SET ended_on = ? WHERE id = ?",
            (date_out(ended.ended_on), ended.id),
        )
        return ended

    def name_of(self, user_id: str) -> str:
        row = self._book.one("SELECT name FROM authorized_user WHERE id = ?", (user_id,))
        if row is None:
            raise NotFoundError("no such authorized user", id=user_id)
        return text_in(row, "name")

    def licence_of(self, user_id: str) -> str | None:
        row = self._book.one("SELECT licence FROM authorized_user WHERE id = ?", (user_id,))
        return None if row is None else maybe_text_in(row, "licence")
