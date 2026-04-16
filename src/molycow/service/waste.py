"""Putting waste away, and getting it back out again months later.

The rule that matters is the last one: a container only leaves as ordinary
rubbish when it has been held its ten half lives and then surveyed at
background with the label off. Either half on its own is not enough, and the
survey is the half people skip because the calendar already said yes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo

from molycow.clock import zone
from molycow.errors import RuleError, SafetyError
from molycow.formulary import formula
from molycow.model.waste import Container, ContainerKind, WasteItem
from molycow.store.audit import AuditRepository
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.waste import ContainerRepository
from molycow.units import Activity

BACKGROUND_MREM = Decimal("0.02")


@dataclass(frozen=True)
class Held:
    """A container in the store and why it is still there."""

    container: Container
    reason: str

    def note(self) -> str:
        return f"{self.container.id} {self.reason}"


class WasteService:
    """The waste store."""

    def __init__(self, book: Book, tz: ZoneInfo | None = None) -> None:
        self._book = book
        self._tz = tz or zone()
        self._containers = ContainerRepository(book)
        self._doses = DoseRepository(book)
        self._audit = AuditRepository(book)

    def open_container(self, kind: ContainerKind, at: dt.datetime) -> Container:
        container = Container(
            id=self._containers.next_id(),
            kind=kind,
            opened_at=at,
        )
        return self._containers.add(container)

    def discard(
        self,
        container_id: str,
        symbol: str,
        activity: Activity,
        at: dt.datetime,
        source: str,
    ) -> Container:
        """Drop something into an open container."""
        container = self._containers.get(container_id)
        if container.is_closed:
            raise RuleError("container-closed", "that container is closed", id=container_id)
        if at < container.opened_at:
            raise RuleError(
                "container-early",
                "that container had not been opened yet",
                id=container_id,
            )
        item = WasteItem(symbol=symbol, activity=activity, added_at=at, source=source)
        return self._containers.add_item(container_id, item)

    def discard_dose(self, container_id: str, dose_id: str, at: dt.datetime) -> Container:
        """Put an unused syringe away at whatever it reads now."""
        dose = self._doses.get(dose_id)
        return self.discard(
            container_id,
            formula(dose.code).nuclide,
            dose.activity_at(at),
            at,
            dose.id,
        )

    def close(self, container_id: str, at: dt.datetime) -> Container:
        return self._containers.close(container_id, at)

    def dispose(
        self,
        container_id: str,
        at: dt.datetime,
        disposed_by: str,
        survey_mrem: Decimal,
    ) -> Container:
        """Take the label off, if the hold and the survey both allow it."""
        container = self._containers.get(container_id)
        if container.is_disposed:
            raise RuleError("container-gone", "that container has already gone", id=container_id)
        held = container.hold_reason(at)
        if held is not None:
            raise RuleError("container-held", f"that container is {held}", id=container_id)
        if survey_mrem > BACKGROUND_MREM:
            raise SafetyError(
                "disposal-survey",
                "that container does not survey at background",
                id=container_id,
                reading=str(survey_mrem),
                background=str(BACKGROUND_MREM),
            )
        with self._book.atomic():
            gone = self._containers.dispose(container_id, at, disposed_by, survey_mrem)
            self._audit.record(
                at,
                disposed_by,
                "disposed",
                container_id,
                f"surveyed {survey_mrem} mrem/h",
            )
        return gone

    def ready(self, at: dt.datetime) -> list[Container]:
        """Containers whose hold has run out and which can be surveyed out."""
        return [one for one in self._containers.in_storage() if one.hold_reason(at) is None]

    def held(self, at: dt.datetime) -> list[Held]:
        """Everything still in the store, with the reason it is still there."""
        found: list[Held] = []
        for container in self._containers.all():
            if container.is_disposed:
                continue
            reason = container.hold_reason(at)
            if reason is not None:
                found.append(Held(container, reason))
        return found

    def activity_in_store(self, at: dt.datetime) -> Activity:
        """What the waste store is holding right now."""
        total = Activity.zero()
        for container in self._containers.all():
            if container.is_disposed:
                continue
            total = total + container.activity_at(at)
        return total

    def container_for(self, kind: ContainerKind, at: dt.datetime) -> Container:
        """The open container of a kind, opening one if there is none."""
        open_ones = self._containers.open_containers(kind)
        if open_ones:
            return open_ones[0]
        return self.open_container(kind, at)
