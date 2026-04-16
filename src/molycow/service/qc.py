"""Running the calibrator checks, and saying when the calibrator may be used.

The expected reading is never typed in. It is the sealed source's certificate
decayed to the day of the check, which is the only number in the check that
nobody in the building can influence.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from molycow.clock import day_of, zone
from molycow.errors import RuleError, SafetyError
from molycow.model.instrument import Instrument
from molycow.model.qc import CheckKind, LinearityPoint, LinearityRun, QcCheck
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.instruments import (
    CheckSourceRepository,
    InstrumentRepository,
    QcRepository,
)
from molycow.units import Activity


@dataclass(frozen=True)
class RunResult:
    """A check that has been run and written down."""

    check: QcCheck
    instrument: Instrument

    @property
    def passes(self) -> bool:
        return self.check.passes

    def note(self) -> str:
        return f"{self.instrument.id} {self.check.note()}"


class QcService:
    """The morning checks, and the ones that come round less often."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._instruments = InstrumentRepository(book)
        self._sources = CheckSourceRepository(book)
        self._checks = QcRepository(book)
        self._audit = AuditRepository(book)

    def run(
        self,
        instrument_id: str,
        kind: CheckKind,
        source_serial: str,
        at: dt.datetime,
        measured: Activity,
        checked_by: str,
    ) -> RunResult:
        """Run one check against a sealed source."""
        instrument = self._instruments.get(instrument_id)
        day = day_of(at, self._tz)
        unusable = instrument.unusable_reason(day)
        if unusable is not None:
            raise RuleError(
                "instrument-unusable",
                f"that instrument cannot be checked: {unusable}",
                instrument=instrument_id,
            )
        source = self._sources.get(source_serial)
        if not source.is_in_use_on(day):
            raise RuleError(
                "source-retired",
                "that check source is not in use that day",
                source=source_serial,
            )
        check = QcCheck(
            instrument_id=instrument_id,
            kind=kind,
            at=at,
            source_serial=source_serial,
            expected=source.activity_on(day),
            measured=measured,
            checked_by=checked_by,
        )
        with self._book.atomic():
            self._checks.add(check)
            self._audit.record(at, checked_by, "checked", instrument_id, check.note())
        return RunResult(check, instrument)

    def constancy(
        self,
        instrument_id: str,
        source_serial: str,
        at: dt.datetime,
        measured: Activity,
        checked_by: str,
    ) -> RunResult:
        return self.run(instrument_id, CheckKind.CONSTANCY, source_serial, at, measured, checked_by)

    def linearity(
        self,
        instrument_id: str,
        symbol: str,
        points: list[LinearityPoint],
        checked_by: str,
    ) -> LinearityRun:
        """Write a linearity run down, whether or not it passed."""
        self._instruments.get(instrument_id)
        run = LinearityRun(
            instrument_id=instrument_id,
            symbol=symbol,
            points=tuple(points),
            checked_by=checked_by,
        )
        self._checks.add_run(run)
        return run

    def passed_on(self, instrument_id: str, kind: CheckKind, day: dt.date) -> bool:
        """Whether a check of that kind passed on that day."""
        return any(one.passes for one in self._checks.on_day(instrument_id, kind, day, self._tz))

    def require_checked(self, instrument_id: str, day: dt.date) -> Instrument:
        """The calibrator, or a stop because the morning check is missing."""
        instrument = self._instruments.get(instrument_id)
        unusable = instrument.unusable_reason(day)
        if unusable is not None:
            raise SafetyError(
                "instrument-unusable",
                f"that instrument cannot be used: {unusable}",
                instrument=instrument_id,
            )
        if not instrument.kind.needs_daily_check:
            return instrument
        if not self.passed_on(instrument_id, CheckKind.CONSTANCY, day):
            raise SafetyError(
                "constancy-missing",
                "that instrument has not passed its constancy check today",
                instrument=instrument_id,
                day=day.isoformat(),
            )
        return instrument

    def overdue(self, instrument_id: str, on: dt.date) -> list[CheckKind]:
        """Which checks have run past their interval, worst first."""
        late: list[CheckKind] = []
        for kind in (CheckKind.CONSTANCY, CheckKind.LINEARITY, CheckKind.ACCURACY):
            last = self._checks.last(instrument_id, kind)
            if last is None:
                late.append(kind)
                continue
            due = last.due_again()
            if due is not None and on >= due:
                late.append(kind)
        return late

    def history(self, instrument_id: str, kind: CheckKind | None = None) -> list[QcCheck]:
        return self._checks.for_instrument(instrument_id, kind)

    def failures(self) -> list[QcCheck]:
        return [one for one in self._checks.all() if not one.passes]
