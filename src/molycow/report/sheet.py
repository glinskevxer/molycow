"""The shape every report in this package comes back in."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    """A heading with rows under it."""

    title: str
    rows: tuple[str, ...] = ()
    empty_note: str = "nothing"

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def lines(self) -> list[str]:
        if self.is_empty:
            return [self.title, f"  {self.empty_note}"]
        return [self.title, *[f"  {row}" for row in self.rows]]


@dataclass(frozen=True)
class Sheet:
    """A titled report made of sections."""

    title: str
    sections: tuple[Section, ...] = field(default_factory=tuple)

    def lines(self) -> list[str]:
        out = [self.title, "=" * len(self.title)]
        for section in self.sections:
            out.append("")
            out.extend(section.lines())
        return out

    def text(self) -> str:
        return "\n".join(self.lines())

    def section(self, title: str) -> Section:
        """One section by its title, or a key error."""
        for section in self.sections:
            if section.title == title:
                return section
        raise KeyError(title)

    def has(self, title: str) -> bool:
        return any(section.title == title for section in self.sections)

    @property
    def row_count(self) -> int:
        return sum(len(section.rows) for section in self.sections)
