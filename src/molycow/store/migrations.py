"""The schema, one numbered step at a time.

Every change to the book is a new migration appended to :data:`MIGRATIONS`.
Nothing here is ever edited once it has shipped, because a book in the field
has already run it and a rewritten step would leave two pharmacies with
different tables and the same version number.

The version lives in sqlite's own ``user_version`` pragma rather than a table
of our own, so a book that has never been migrated reads as version zero
without anything having to exist first.
"""

from __future__ import annotations

from dataclasses import dataclass

from molycow.errors import MolycowError
from molycow.store.book import Book


@dataclass(frozen=True)
class Migration:
    """One numbered step, with the statements that carry it out."""

    number: int
    name: str
    statements: str


CORE_REGISTER = """
CREATE TABLE customer (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  kind        TEXT NOT NULL CHECK (kind IN ('hospital', 'clinic', 'imaging', 'research')),
  licence     TEXT NOT NULL,
  street      TEXT NOT NULL,
  town        TEXT NOT NULL,
  zone        TEXT NOT NULL,
  opened_on   TEXT NOT NULL,
  closed_on   TEXT
);

CREATE TABLE authorized_user (
  id          TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customer(id),
  name        TEXT NOT NULL,
  licence     TEXT NOT NULL,
  added_on    TEXT NOT NULL,
  ended_on    TEXT,
  UNIQUE (customer_id, name)
);

CREATE TABLE authorized_nuclide (
  user_id     TEXT NOT NULL REFERENCES authorized_user(id) ON DELETE CASCADE,
  nuclide     TEXT NOT NULL,
  PRIMARY KEY (user_id, nuclide)
);

CREATE INDEX customer_by_zone ON customer(zone);
CREATE INDEX authorized_user_by_customer ON authorized_user(customer_id);
"""


GENERATOR_BENCH = """
CREATE TABLE generator (
  id                  TEXT PRIMARY KEY,
  serial              TEXT NOT NULL UNIQUE,
  maker               TEXT NOT NULL,
  calibrated_at       TEXT NOT NULL,
  calibrated_activity TEXT NOT NULL,
  received_on         TEXT NOT NULL,
  expires_on          TEXT NOT NULL,
  retired_on          TEXT
);

CREATE TABLE elution (
  id           TEXT PRIMARY KEY,
  generator_id TEXT NOT NULL REFERENCES generator(id),
  drawn_at     TEXT NOT NULL,
  volume       TEXT NOT NULL,
  activity     TEXT NOT NULL,
  expected     TEXT NOT NULL,
  residual     TEXT NOT NULL
);

CREATE INDEX elution_by_generator ON elution(generator_id, drawn_at);
CREATE INDEX generator_by_expiry ON generator(expires_on);
"""


ELUATE_TESTS = """
CREATE TABLE breakthrough (
  elution_id    TEXT PRIMARY KEY REFERENCES elution(id),
  tested_at     TEXT NOT NULL,
  moly          TEXT NOT NULL,
  technetium    TEXT NOT NULL,
  aluminium_ppm TEXT NOT NULL,
  tested_by     TEXT NOT NULL
);
"""


COMPOUNDING = """
CREATE TABLE kit_lot (
  id          TEXT PRIMARY KEY,
  code        TEXT NOT NULL,
  maker       TEXT NOT NULL,
  lot         TEXT NOT NULL,
  received_on TEXT NOT NULL,
  expires_on  TEXT NOT NULL,
  vials       INTEGER NOT NULL,
  UNIQUE (code, lot)
);

CREATE TABLE batch (
  id          TEXT PRIMARY KEY,
  kit_lot_id  TEXT NOT NULL REFERENCES kit_lot(id),
  elution_id  TEXT NOT NULL REFERENCES elution(id),
  code        TEXT NOT NULL,
  made_at     TEXT NOT NULL,
  activity    TEXT NOT NULL,
  volume      TEXT NOT NULL,
  made_by     TEXT NOT NULL,
  rcp         TEXT
);

CREATE INDEX batch_by_elution ON batch(elution_id);
CREATE INDEX batch_by_made_at ON batch(made_at);
CREATE INDEX kit_lot_by_code ON kit_lot(code, expires_on);
"""


SALINE_ON_BATCHES = """
ALTER TABLE batch ADD COLUMN eluate_volume TEXT NOT NULL DEFAULT '0';

UPDATE batch SET eluate_volume = volume WHERE eluate_volume = '0';
"""


PURITY_STRIPS = """
CREATE TABLE purity_test (
  batch_id           TEXT PRIMARY KEY REFERENCES batch(id),
  tested_at          TEXT NOT NULL,
  solvent_origin     INTEGER NOT NULL,
  solvent_front      INTEGER NOT NULL,
  solvent_background INTEGER NOT NULL,
  saline_origin      INTEGER NOT NULL,
  saline_front       INTEGER NOT NULL,
  saline_background  INTEGER NOT NULL,
  tested_by          TEXT NOT NULL
);
"""


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "core register", CORE_REGISTER),
    Migration(2, "generator bench", GENERATOR_BENCH),
    Migration(3, "eluate tests", ELUATE_TESTS),
    Migration(4, "compounding", COMPOUNDING),
    Migration(5, "saline on batches", SALINE_ON_BATCHES),
    Migration(6, "purity strips", PURITY_STRIPS),
)


def latest() -> int:
    """The version a fully migrated book reads."""
    return MIGRATIONS[-1].number if MIGRATIONS else 0


def schema_version(book: Book) -> int:
    """What version the book is at now."""
    value = book.value("PRAGMA user_version")
    return int(value or 0)


def pending(book: Book) -> tuple[Migration, ...]:
    """The steps this book has not run yet, in order."""
    at = schema_version(book)
    return tuple(step for step in MIGRATIONS if step.number > at)


def is_current(book: Book) -> bool:
    return schema_version(book) == latest()


def apply(book: Book, upto: int | None = None) -> tuple[Migration, ...]:
    """Run the pending steps, each one inside its own savepoint.

    A step that fails leaves the book at the version before it, which is the
    only state a half applied schema is allowed to be in.
    """
    target = latest() if upto is None else upto
    if target > latest():
        raise MolycowError(f"there is no migration {target}, the last one is {latest()}")
    ran: list[Migration] = []
    for step in pending(book):
        if step.number > target:
            break
        with book.atomic():
            book.script(step.statements)
            book.execute(f"PRAGMA user_version = {step.number}")
        ran.append(step)
    return tuple(ran)


def require_current(book: Book) -> None:
    """Refuse to work against a book that is behind the code."""
    at = schema_version(book)
    if at != latest():
        raise MolycowError(
            "this book is not at the schema this build expects",
            at=at,
            wanted=latest(),
        )


def numbers() -> tuple[int, ...]:
    return tuple(step.number for step in MIGRATIONS)
