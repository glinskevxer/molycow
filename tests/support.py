"""Builders that put a working day in the book.

Every test that needs a batch needs a generator, an elution, a breakthrough
test and a kit lot first, and writing that out per file left the same forty
lines in six places. It lives here instead, so a schema change breaks one file.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from molycow.model import AuthorizedUser, Customer, CustomerKind
from molycow.model.generator import Generator
from molycow.model.kit import KitLot
from molycow.model.order import Order
from molycow.model.purity import Strip, System
from molycow.service.breakthrough import BreakthroughService
from molycow.service.compound import CompoundService
from molycow.service.elution import ElutionService
from molycow.service.purity import PurityService
from molycow.store import Book
from molycow.store.generators import GeneratorRepository
from molycow.store.kits import KitLotRepository
from molycow.store.orders import OrderRepository
from molycow.store.register import AuthorizedUserRepository, CustomerRepository
from molycow.units import Activity, Volume
from tests.conftest import at

DAY = dt.date(2025, 4, 8)
MILKED = at("2025-04-08 06:30")
TESTED = at("2025-04-08 06:45")
PREPPED = at("2025-04-08 07:15")
STRIPPED = at("2025-04-08 07:30")
CALIBRATION = at("2025-04-08 09:00")
ORDERED = at("2025-04-07 16:10")

CLEAN_SOLVENT = Strip(System.SOLVENT, origin=48200, front=1100)
CLEAN_SALINE = Strip(System.SALINE, origin=900, front=47600)


def a_customer(book: Book, **changed: object) -> Customer:
    fields: dict[str, object] = {
        "id": "CU-0001",
        "name": "Saint Brannon Medical Centre",
        "kind": CustomerKind.HOSPITAL,
        "licence": "42-28931-01",
        "street": "1400 Weir Street",
        "town": "Ardmore",
        "zone": "north",
        "opened_on": dt.date(2025, 1, 6),
    }
    fields.update(changed)
    return CustomerRepository(book).add(Customer(**fields))  # type: ignore[arg-type]


def an_authorized_user(book: Book, **changed: object) -> AuthorizedUser:
    fields: dict[str, object] = {
        "id": "AU-0004",
        "customer_id": "CU-0001",
        "name": "R. Okonkwo",
        "licence": "42-28931-01",
        "added_on": dt.date(2025, 1, 6),
        "nuclides": frozenset({"Tc-99m"}),
    }
    fields.update(changed)
    return AuthorizedUserRepository(book).add(AuthorizedUser(**fields))  # type: ignore[arg-type]


def a_register(book: Book, **changed: object) -> Customer:
    """A customer with a physician named on it."""
    customer = a_customer(book, **changed)
    an_authorized_user(book)
    return customer


def a_generator(book: Book, generator_id: str = "GEN-0027", **changed: object) -> Generator:
    fields: dict[str, object] = {
        "id": generator_id,
        "serial": f"M99-{generator_id[-4:]}",
        "maker": "Corren Isotopes",
        "calibrated_at": at("2025-04-05 12:00"),
        "calibrated_activity": Activity.of(2, "Ci"),
        "received_on": dt.date(2025, 4, 5),
        "expires_on": dt.date(2025, 4, 19),
    }
    fields.update(changed)
    return GeneratorRepository(book).add(Generator(**fields))  # type: ignore[arg-type]


def a_kit_lot(book: Book, lot_id: str = "KL-0114", **changed: object) -> KitLot:
    fields: dict[str, object] = {
        "id": lot_id,
        "code": "MDP",
        "maker": "Sedgwick Radiochem",
        "lot": f"9F{lot_id[-4:]}",
        "received_on": dt.date(2025, 3, 20),
        "expires_on": dt.date(2026, 3, 31),
        "vials": 30,
    }
    fields.update(changed)
    return KitLotRepository(book).add(KitLot(**fields))  # type: ignore[arg-type]


def an_elution(book: Book, tested: bool = True, generator_id: str = "GEN-0027") -> str:
    """A milked column, tested unless the test asks for an untested one."""
    if GeneratorRepository(book).find(generator_id) is None:
        a_generator(book, generator_id)
    milking = ElutionService(book).milk(
        generator_id, MILKED, Volume.of(10), Activity.of(940, "mCi")
    )
    if tested:
        BreakthroughService(book).test(
            milking.elution.id, TESTED, Activity.of("0.9", "uci"), Decimal(4), "K. Ruzicka"
        )
    return milking.elution.id


def a_batch(book: Book, code: str = "MDP", activity: Activity | None = None) -> str:
    """A compounded batch, with no purity reading on it yet."""
    elution_id = an_elution(book)
    if KitLotRepository(book).oldest_in_date(code, DAY) is None:
        a_kit_lot(book, "KL-0114", code=code)
    batch = CompoundService(book).compound(
        code, elution_id, PREPPED, activity or Activity.of(300, "mci"), "K. Ruzicka"
    )
    return batch.id


def a_released_batch(book: Book, code: str = "MDP") -> str:
    """A batch with both strips run and the purity written on it."""
    batch_id = a_batch(book, code)
    PurityService(book).run(batch_id, STRIPPED, CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka")
    return batch_id


def an_order(book: Book, order_id: str = "ORD-250407-11", **changed: object) -> Order:
    fields: dict[str, object] = {
        "id": order_id,
        "customer_id": "CU-0001",
        "user_id": "AU-0004",
        "code": "MDP",
        "procedure": "whole body bone",
        "patient_ref": "A-4471902",
        "activity": Activity.of(22, "mci"),
        "calibration_at": CALIBRATION,
        "ordered_at": ORDERED,
    }
    fields.update(changed)
    return OrderRepository(book).add(Order(**fields))  # type: ignore[arg-type]


@dataclass(frozen=True)
class Day:
    """The identifiers a full day's setup left in the book."""

    order_id: str
    batch_id: str


def a_working_day(book: Book) -> Day:
    """Register, column, eluate, kit, released batch and an open order."""
    a_register(book)
    batch_id = a_released_batch(book)
    order = an_order(book)
    return Day(order.id, batch_id)
