"""Who did what, to which record, and when.

An inspector's first question is not what the book says now, it is who changed
it and when. The trail is append only: nothing in this package ever edits or
deletes an entry, because a trail that can be tidied is not a trail.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from molycow.clock import stamp
from molycow.errors import ValidationError
from molycow.ids import normalise, parse

ACTIONS = (
    "milked",
    "tested",
    "compounded",
    "released",
    "held",
    "drew",
    "packed",
    "delivered",
    "discarded",
    "disposed",
    "surveyed",
    "checked",
    "cancelled",
    "amended",
)


@dataclass(frozen=True)
class Entry:
    """One line of the trail."""

    at: dt.datetime
    actor: str
    action: str
    subject: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.actor.strip():
            raise ValidationError("an entry says who did it", action=self.action)
        if self.action not in ACTIONS:
            raise ValidationError(
                "that is not one of the actions the trail records",
                action=self.action,
                actions=", ".join(ACTIONS),
            )
        object.__setattr__(self, "subject", normalise(self.subject))
        parse(self.subject)

    def line(self, tz: object = None) -> str:
        """The line the trail prints."""
        from zoneinfo import ZoneInfo

        where = tz if isinstance(tz, ZoneInfo) else None
        when = stamp(self.at, where)
        detail = f"  {self.detail}" if self.detail else ""
        return f"{when}  {self.actor:14} {self.action:11} {self.subject}{detail}"
