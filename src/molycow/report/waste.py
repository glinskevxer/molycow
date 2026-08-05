"""The waste store, as the inspector asks about it.

Two questions, and they are not the same one. What is in the store now and
when each drum clears, and what has left the building with what reading
against it. The second is the one that has to be kept for years.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from molycow.clock import stamp, zone
from molycow.report.sheet import Section, Sheet
from molycow.service.waste import WasteService
from molycow.store.book import Book
from molycow.store.waste import ContainerRepository


def waste_sheet(book: Book, at: dt.datetime, tz: ZoneInfo | None = None) -> Sheet:
    """The state of the store at a moment, and everything that has gone out."""
    where = tz or zone()
    service = WasteService(book, where)
    containers = ContainerRepository(book)
    holding = []
    for held in service.held(at):
        container = held.container
        clear = container.clear_at
        when = "nothing in it yet" if clear is None else stamp(clear, where)
        holding.append(
            f"{container.id}  {container.kind.value:7} {len(container.items):3d} items  "
            f"{container.activity_at(at).format('mci', 2):>12}  clears {when}  {held.reason}"
        )
    ready = [
        f"{one.id}  {one.kind.value:7} ready to survey out, "
        f"{one.activity_at(at).format('uci', 1)} left"
        for one in service.ready(at)
    ]
    gone = []
    for container in containers.all():
        if not container.is_disposed or container.disposed_at is None:
            continue
        survey = containers.disposal_survey(container.id)
        gone.append(
            f"{container.id}  {container.kind.value:7} "
            f"{stamp(container.disposed_at, where)}  "
            f"surveyed {survey} mrem/h  by {containers.disposed_by(container.id)}"
        )
    return Sheet(
        title=f"waste store {stamp(at, where)}",
        sections=(
            Section("holding", tuple(holding), "nothing is holding"),
            Section("ready", tuple(ready), "nothing is ready to go"),
            Section("disposed of", tuple(gone), "nothing has left"),
            Section(
                "in the store",
                (f"{service.activity_in_store(at).format('mci', 2)} altogether",),
            ),
        ),
    )
