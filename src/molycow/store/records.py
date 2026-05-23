"""What every repository in this package has in common.

Each repository owns one table and knows how to turn its rows into records.
The book it reads, and the way it refuses a record that is not there, are the
same in all of them, and were written out fifteen times before this existed.
"""

from __future__ import annotations

from typing import TypeVar

from molycow.errors import NotFoundError
from molycow.store.book import Book

Record = TypeVar("Record")


class Records:
    """A repository over one table of the book."""

    def __init__(self, book: Book) -> None:
        self._book = book

    @property
    def book(self) -> Book:
        """The book this repository reads and writes."""
        return self._book

    def required(self, found: Record | None, message: str, **detail: object) -> Record:
        """Give back what was found, or refuse with the words the caller wants."""
        if found is None:
            raise NotFoundError(message, **detail)
        return found
