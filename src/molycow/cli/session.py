"""What every command needs: where the book is and what time zone it runs in."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from molycow.clock import DEFAULT_ZONE, SystemClock, zone
from molycow.errors import MolycowError
from molycow.store import Book
from molycow.store.migrations import is_current, latest, schema_version


@dataclass(frozen=True)
class Session:
    """The settings a command was invoked with."""

    path: Path
    zone_name: str = DEFAULT_ZONE

    @property
    def tz(self) -> ZoneInfo:
        return zone(self.zone_name)

    @property
    def clock(self) -> SystemClock:
        return SystemClock()

    @contextmanager
    def open(self, migrated: bool = True) -> Iterator[Book]:
        """Open the book, and refuse one that is behind this build."""
        if not self.path.exists():
            raise MolycowError(f"there is no book at {self.path}, run 'molycow book init' first")
        with Book.open(self.path) as book:
            if migrated and not is_current(book):
                raise MolycowError(
                    f"that book is at schema {schema_version(book)} "
                    f"and this build wants {latest()}, run 'molycow book migrate'"
                )
            yield book

    @contextmanager
    def create(self) -> Iterator[Book]:
        """Open the book for the first time, making the file if it is not there."""
        with Book.open(self.path) as book:
            yield book
