"""Reading the possession limits off the licence."""

from __future__ import annotations

from molycow.errors import NotFoundError
from molycow.model.licence import PossessionLimit
from molycow.store.book import Book
from molycow.store.rows import decimal_in, decimal_out, text_in
from molycow.units import Activity


class LicenceRepository:
    """The nuclides the licence names, and the ceiling on each."""

    def __init__(self, book: Book) -> None:
        self._book = book

    def find(self, symbol: str) -> PossessionLimit | None:
        row = self._book.one("SELECT * FROM possession_limit WHERE symbol = ?", (symbol,))
        if row is None:
            return None
        return PossessionLimit(
            symbol=text_in(row, "symbol"),
            limit=Activity.of(decimal_in(row["curies"], "curies"), "ci"),
            note=text_in(row, "note"),
        )

    def get(self, symbol: str) -> PossessionLimit:
        """One possession limit, or a refusal if it is not in the book."""
        found = self.find(symbol)
        if found is None:
            raise NotFoundError("the licence does not name that nuclide", symbol=symbol)
        return found

    def all(self) -> list[PossessionLimit]:
        rows = self._book.all("SELECT symbol FROM possession_limit ORDER BY symbol")
        return [self.get(str(row["symbol"])) for row in rows]

    def names(self) -> list[str]:
        return [one.symbol for one in self.all()]

    def set_limit(self, symbol: str, curies: object, note: str) -> PossessionLimit:
        """Change a ceiling, which happens when the licence is amended."""
        limit = PossessionLimit(symbol, Activity.of(curies, "ci"), note)
        self._book.execute(
            """
            INSERT INTO possession_limit (symbol, curies, note) VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET curies = excluded.curies, note = excluded.note
            """,
            (limit.symbol, decimal_out(limit.limit.ci_value), note),
        )
        return limit
