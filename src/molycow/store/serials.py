"""Handing out the next label number, in one place.

Every repository used to read its own table's ids, hand them to
``ids.next_serial`` and build the number itself. That was the same four lines
nine times over, and it is the sort of thing that stays the same everywhere
right up until one of them quietly does not.
"""

from __future__ import annotations

import datetime as dt

from molycow.ids import Kind, make, next_serial
from molycow.store.book import Book

TABLES: dict[Kind, str] = {
    Kind.CUSTOMER: "customer",
    Kind.AUTHORIZED_USER: "authorized_user",
    Kind.INSTRUMENT: "instrument",
    Kind.GENERATOR: "generator",
    Kind.KIT_LOT: "kit_lot",
    Kind.CONTAINER: "container",
    Kind.ROUTE: "route",
    Kind.ELUTION: "elution",
    Kind.BATCH: "batch",
    Kind.DOSE: "dose",
    Kind.ORDER: "customer_order",
    Kind.SURVEY: "survey",
    Kind.SHIPMENT: "shipment",
}


def issued(book: Book, kind: Kind) -> list[str]:
    """Every number of one kind the book has already handed out."""
    table = TABLES[kind]
    return [str(row["id"]) for row in book.all(f"SELECT id FROM {table}")]


def next_id(book: Book, kind: Kind, day: dt.date | None = None) -> str:
    """The next number of a kind, restarting daily where the kind says so."""
    return make(kind, next_serial(issued(book, kind), kind, day), day)
