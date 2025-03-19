"""Fixtures every test can reach for.

The book fixture is a migrated in memory pharmacy book. Tests that want rows
in it build them through the repositories rather than by writing sql, so a
schema change breaks the repository and not fifty tests.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from molycow.clock import parse_moment, zone
from molycow.store import Book
from molycow.store.migrations import apply

PHARMACY_ZONE = zone()


@pytest.fixture
def book() -> Iterator[Book]:
    with Book.in_memory() as opened:
        apply(opened)
        yield opened


@pytest.fixture
def tz() -> object:
    return PHARMACY_ZONE


@pytest.fixture
def today() -> dt.date:
    return dt.date(2025, 4, 8)


@pytest.fixture
def morning() -> dt.datetime:
    return parse_moment("2025-04-08 06:30", PHARMACY_ZONE)


def at(text: str) -> dt.datetime:
    """A local moment, written the way the bench writes it."""
    return parse_moment(text, PHARMACY_ZONE)
