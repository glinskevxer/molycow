"""Where the pharmacy's records are kept.

One sqlite file holds the whole book. Everything above this package talks to
repositories, so the only place that knows sqlite exists is in here.
"""

from molycow.store.book import Book

__all__ = ["Book"]
