"""Turning the columns sqlite hands back into the values the model wants.

sqlite has no date type and no decimal type, so everything is stored as text
and read back through here. Doing it in one place is what keeps a date written
by one repository readable by another.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from decimal import Decimal, InvalidOperation

from molycow.errors import ValidationError
from molycow.units import Activity, Volume


def date_out(value: dt.date | None) -> str | None:
    """Store a date as the text sqlite keeps."""
    return None if value is None else value.isoformat()


def date_in(value: object, column: str) -> dt.date:
    """Read a date back out of a column, or refuse what is in it."""
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            raise ValidationError("that column does not hold a date", column=column) from None
    raise ValidationError("that column does not hold a date", column=column, value=repr(value))


def maybe_date_in(value: object, column: str) -> dt.date | None:
    """The same as a date, allowing the column to be null."""
    return None if value is None else date_in(value, column)


def moment_out(value: dt.datetime) -> str:
    """Store an aware moment as UTC text so it sorts in the order it happened."""
    if value.tzinfo is None:
        raise ValidationError("a moment without a zone cannot be stored", column="moment")
    return value.astimezone(dt.UTC).isoformat()


def moment_in(value: object, column: str) -> dt.datetime:
    """Read an aware moment back, refusing one that lost its zone."""
    if isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value)
        except ValueError:
            raise ValidationError("that column does not hold a moment", column=column) from None
        if parsed.tzinfo is None:
            raise ValidationError("a stored moment has lost its zone", column=column)
        return parsed
    raise ValidationError("that column does not hold a moment", column=column, value=repr(value))


def maybe_moment_in(value: object, column: str) -> dt.datetime | None:
    """The same as a moment, allowing the column to be null."""
    return None if value is None else moment_in(value, column)


def decimal_out(value: Decimal) -> str:
    """Store a decimal without going anywhere near a float."""
    return str(value)


def decimal_in(value: object, column: str) -> Decimal:
    """Read a decimal back, or refuse what is in the column."""
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise ValidationError("that column does not hold a number", column=column) from None


def activity_out(value: Activity) -> str:
    """Store an activity as its microcuries."""
    return str(value.uci)


def activity_in(value: object, column: str) -> Activity:
    """Read an activity back out of a column."""
    return Activity(decimal_in(value, column))


def maybe_activity_in(value: object, column: str) -> Activity | None:
    """The same as an activity, allowing the column to be null."""
    return None if value is None else activity_in(value, column)


def volume_out(value: Volume) -> str:
    """Store a volume as its millilitres."""
    return str(value.ml)


def volume_in(value: object, column: str) -> Volume:
    """Read a volume back out of a column."""
    return Volume(decimal_in(value, column))


def text_in(row: sqlite3.Row, column: str) -> str:
    """Read a text column, refusing a column that holds something else."""
    value = row[column]
    if not isinstance(value, str):
        raise ValidationError("that column does not hold text", column=column)
    return value


def maybe_text_in(row: sqlite3.Row, column: str) -> str | None:
    """The same as text, allowing the column to be null."""
    value = row[column]
    if value is None:
        return None
    return text_in(row, column)


def flag_out(value: bool) -> int:
    """Store a flag as the zero or one sqlite understands."""
    return 1 if value else 0


def flag_in(value: object, column: str) -> bool:
    """Read a flag back, refusing anything that is not a zero or a one."""
    if value in (0, 1):
        return bool(value)
    raise ValidationError("that column does not hold a flag", column=column, value=repr(value))
