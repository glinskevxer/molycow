"""Writing a day out as csv, for the people who want it in a spreadsheet.

Every file is one row per record with the identifiers spelled out, because the
first thing anybody does with an export is join it against something else. The
numbers go out as they are stored, in microcuries and millilitres, so nothing
is rounded twice on the way to a pivot table.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from molycow.clock import stamp, zone
from molycow.store.book import Book
from molycow.store.doses import DoseRepository
from molycow.store.generators import ElutionRepository
from molycow.store.kits import BatchRepository
from molycow.store.orders import OrderRepository
from molycow.store.shipments import ShipmentRepository


@dataclass(frozen=True)
class Written:
    """One file the export produced."""

    path: Path
    rows: int

    def line(self) -> str:
        """The line the command prints for this file."""
        return f"{self.rows:5d}  {self.path.name}"


def _write(folder: Path, name: str, header: list[str], rows: list[list[str]]) -> Written:
    target = folder / f"{name}.csv"
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return Written(target, len(rows))


def export_day(book: Book, day: dt.date, folder: Path, tz: ZoneInfo | None = None) -> list[Written]:
    """Write a day's records into a folder as csv, and say what was written."""
    where = tz or zone()
    folder.mkdir(parents=True, exist_ok=True)
    written = [
        _write(
            folder,
            "elutions",
            ["id", "generator", "drawn_at", "activity_uci", "volume_ml", "expected_uci"],
            [
                [
                    one.id,
                    one.generator_id,
                    stamp(one.drawn_at, where),
                    str(one.activity.uci),
                    str(one.volume.ml),
                    str(one.expected.uci),
                ]
                for one in ElutionRepository(book).on_day(day, where)
            ],
        ),
        _write(
            folder,
            "batches",
            ["id", "code", "kit_lot", "elution", "made_at", "activity_uci", "volume_ml", "rcp"],
            [
                [
                    one.id,
                    one.code,
                    one.kit_lot_id,
                    one.elution_id,
                    stamp(one.made_at, where),
                    str(one.activity.uci),
                    str(one.volume.ml),
                    "" if one.rcp is None else str(one.rcp),
                ]
                for one in BatchRepository(book).on_day(day, where)
            ],
        ),
    ]
    orders = OrderRepository(book)
    written.append(
        _write(
            folder,
            "doses",
            [
                "id",
                "order",
                "customer",
                "patient_ref",
                "batch",
                "code",
                "drawn_at",
                "calibration_at",
                "volume_ml",
                "assayed_uci",
                "variance_percent",
            ],
            [
                [
                    one.id,
                    one.order_id,
                    orders.get(one.order_id).customer_id,
                    orders.get(one.order_id).patient_ref,
                    one.batch_id,
                    one.code,
                    stamp(one.drawn_at, where),
                    stamp(one.calibration_at, where),
                    str(one.volume.ml),
                    str(one.assayed.uci),
                    str(one.variance_from(orders.get(one.order_id).activity)),
                ]
                for one in DoseRepository(book).on_day(day, where)
            ],
        )
    )
    written.append(
        _write(
            folder,
            "shipments",
            ["id", "customer", "packed_at", "doses", "label", "transport_index", "delivered_at"],
            [
                [
                    one.id,
                    one.customer_id,
                    stamp(one.packed_at, where),
                    str(one.dose_count),
                    one.label.value,
                    str(one.transport_index),
                    "" if one.delivered_at is None else stamp(one.delivered_at, where),
                ]
                for one in ShipmentRepository(book).on_day(day, where)
            ],
        )
    )
    return written
