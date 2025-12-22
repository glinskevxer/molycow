"""The sqlite file the pharmacy writes to, and the rules for opening it.

A ``Book`` owns one connection. Foreign keys are on, which sqlite does not do
by itself, and writes go through :meth:`Book.atomic` so a pair of rows that
belong together cannot land half done. It nests, because a service that writes
two records often calls another that writes one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any

from molycow.errors import ConflictError, MolycowError, ValidationError

Row = sqlite3.Row
Params = Sequence[Any] | dict[str, Any]


class Book:
    """One open pharmacy book."""

    def __init__(self, connection: sqlite3.Connection, path: Path | None = None) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._path = path
        self._savepoints = 0
        self._closed = False
        self._prepare()

    @classmethod
    def open(cls, path: Path | str) -> Book:
        """Open, or create, the book at a path."""
        target = Path(path)
        if target.parent and not target.parent.exists():
            raise ValidationError("there is no folder to put the book in", path=str(target))
        return cls(sqlite3.connect(target, isolation_level=None), target)

    @classmethod
    def in_memory(cls) -> Book:
        """A book that lives only as long as the process, for tests and dry runs."""
        return cls(sqlite3.connect(":memory:", isolation_level=None))

    def _prepare(self) -> None:
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        if self._path is not None:
            self._connection.execute("PRAGMA journal_mode = WAL")
        else:
            self._connection.execute("PRAGMA synchronous = OFF")

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def closed(self) -> bool:
        return self._closed

    def execute(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        """Run one statement, turning sqlite's own complaints into ours."""
        self._require_open()
        try:
            return self._connection.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise _integrity(exc) from None
        except sqlite3.OperationalError as exc:
            raise MolycowError(f"the book would not take that: {exc}") from None

    def execute_many(self, sql: str, rows: Sequence[Params]) -> None:
        """Run one statement over many rows of parameters."""
        self._require_open()
        try:
            self._connection.executemany(sql, rows)
        except sqlite3.IntegrityError as exc:
            raise _integrity(exc) from None

    def script(self, sql: str) -> None:
        """Run a whole statement block, which is how migrations are written.

        The statements are split and run one at a time on purpose. sqlite's own
        ``executescript`` commits whatever transaction is open before it starts,
        which silently throws away the savepoint a migration is meant to be
        running inside.
        """
        self._require_open()
        for statement in split_statements(sql):
            self.execute(statement)

    def one(self, sql: str, params: Params = ()) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self.execute(sql, params).fetchone()
        return row

    def all(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        return list(self.execute(sql, params).fetchall())

    def value(self, sql: str, params: Params = ()) -> Any:
        """The first column of the first row, or ``None``."""
        row = self.one(sql, params)
        return None if row is None else row[0]

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """A savepoint around a group of writes, safe to nest."""
        self._require_open()
        name = f"mc_{self._savepoints}"
        self._savepoints += 1
        self._connection.execute(f"SAVEPOINT {name}")
        try:
            yield
        except BaseException:
            self._connection.execute(f"ROLLBACK TO {name}")
            self._connection.execute(f"RELEASE {name}")
            self._savepoints -= 1
            raise
        self._connection.execute(f"RELEASE {name}")
        self._savepoints -= 1

    def close(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise MolycowError("the book is closed")

    def __enter__(self) -> Book:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()


def split_statements(sql: str) -> list[str]:
    """Cut a block of sql into whole statements."""
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    tail = buffer.strip()
    if tail:
        raise ValidationError("that sql block ends part way through a statement", tail=tail[:60])
    return statements


def _integrity(exc: sqlite3.IntegrityError) -> MolycowError:
    text = str(exc)
    if "UNIQUE" in text:
        return ConflictError("that record is already in the book", detail=text)
    if "FOREIGN KEY" in text:
        return ValidationError("that record points at something that is not there", detail=text)
    return ValidationError(f"the book refused that record: {text}")
