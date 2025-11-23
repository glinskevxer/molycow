"""Driving the command line the way a working morning drives it.

Every command test needs a book with a customer, a column, an eluate, a kit
and a calibrator in it. Doing that through the cli rather than through the
repositories is deliberate: it means the commands are exercised in the order a
technologist runs them, and a command that quietly stops working is caught by
the next test that needs its output.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from click.testing import CliRunner, Result
from tests.conftest import at

from molycow.cli.main import run
from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
from molycow.model.qc import CheckKind, QcCheck
from molycow.store import Book
from molycow.store.instruments import CheckSourceRepository, InstrumentRepository, QcRepository
from molycow.units import Activity


def call(runner: CliRunner, bookfile: Path, *args: str) -> Result:
    return runner.invoke(run, ["--book", str(bookfile), *args])


def a_book(runner: CliRunner, tmp_path: Path) -> Path:
    target = tmp_path / "day.sqlite3"
    call(runner, target, "book", "init")
    return target


def a_customer(runner: CliRunner, bookfile: Path, name: str = "Saint Brannon") -> Result:
    return call(
        runner,
        bookfile,
        "customer",
        "add",
        name,
        "--kind",
        "hospital",
        "--licence",
        "42-28931-01",
        "--street",
        "1400 Weir Street",
        "--town",
        "Ardmore",
        "--zone",
        "north",
        "--opened",
        "2025-01-06",
    )


def a_physician(runner: CliRunner, bookfile: Path, customer_id: str = "CU-0001") -> Result:
    return call(
        runner,
        bookfile,
        "physician",
        "add",
        customer_id,
        "R. Okonkwo",
        "--licence",
        "42-28931-01",
        "--nuclide",
        "Tc-99m",
        "--added",
        "2025-01-06",
    )


def an_order(
    runner: CliRunner,
    bookfile: Path,
    ref: str = "A-4471902",
    calibration: str = "2025-04-08 09:00",
) -> Result:
    return call(
        runner,
        bookfile,
        "order",
        "take",
        "CU-0001",
        "AU-0001",
        "--code",
        "MDP",
        "--procedure",
        "whole body bone",
        "--ref",
        ref,
        "--activity",
        "22 mCi",
        "--calibration",
        calibration,
        "--at",
        "2025-04-07 16:10",
    )


def a_calibrator(bookfile: Path, instrument_id: str = "IC-0003", checked: bool = True) -> str:
    """A calibrator with this morning's constancy check on it."""
    with Book.open(bookfile) as book:
        InstrumentRepository(book).add(
            Instrument(
                id=instrument_id,
                kind=InstrumentKind.DOSE_CALIBRATOR,
                maker="Vernay",
                model="CRC-55tR",
                serial=f"551-{instrument_id[-4:]}",
                installed_on=dt.date(2023, 6, 12),
                calibrated_on=dt.date(2025, 2, 3),
            )
        )
        sources = CheckSourceRepository(book)
        if sources.find("CS-9912") is None:
            sources.add(
                CheckSource(
                    serial="CS-9912",
                    symbol="Cs-137",
                    certified_activity=Activity.of(200, "uci"),
                    certified_on=dt.date(2019, 7, 1),
                )
            )
        if checked:
            reading = sources.get("CS-9912").activity_on(dt.date(2025, 4, 8))
            QcRepository(book).add(
                QcCheck(
                    instrument_id=instrument_id,
                    kind=CheckKind.CONSTANCY,
                    at=at("2025-04-08 06:05"),
                    source_serial="CS-9912",
                    expected=reading,
                    measured=reading,
                    checked_by="K. Ruzicka",
                )
            )
    return instrument_id


def a_bench(runner: CliRunner, bookfile: Path) -> None:
    """A milked, tested column and a kit lot on the shelf."""
    call(
        runner,
        bookfile,
        "generator",
        "receive",
        "M99-44182",
        "--maker",
        "Corren Isotopes",
        "--activity",
        "2 Ci",
        "--calibrated",
        "2025-04-05 12:00",
        "--received",
        "2025-04-05",
        "--expires",
        "2025-04-19",
    )
    call(
        runner,
        bookfile,
        "generator",
        "milk",
        "GEN-0001",
        "--at",
        "2025-04-08 06:30",
        "--volume",
        "10 mL",
        "--activity",
        "940 mCi",
    )
    call(
        runner,
        bookfile,
        "generator",
        "test",
        "EL-250408-01",
        "--at",
        "2025-04-08 06:45",
        "--moly",
        "0.9 uCi",
        "--aluminium",
        "4",
        "--by",
        "K. Ruzicka",
    )
    call(
        runner,
        bookfile,
        "kit",
        "add",
        "MDP",
        "9F4471",
        "--maker",
        "Sedgwick",
        "--received",
        "2025-03-20",
        "--expires",
        "2026-03-31",
        "--vials",
        "30",
    )


def a_released_batch(runner: CliRunner, bookfile: Path) -> str:
    call(
        runner,
        bookfile,
        "kit",
        "compound",
        "MDP",
        "EL-250408-01",
        "--at",
        "2025-04-08 07:15",
        "--activity",
        "300 mCi",
        "--by",
        "K. Ruzicka",
    )
    call(
        runner,
        bookfile,
        "kit",
        "strips",
        "B-250408-01",
        "--at",
        "2025-04-08 07:35",
        "--solvent",
        "48200",
        "1100",
        "--saline",
        "900",
        "47600",
        "--by",
        "K. Ruzicka",
    )
    return "B-250408-01"


def a_drawn_dose(runner: CliRunner, bookfile: Path, assay: str = "23.09 mCi") -> Result:
    return call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        assay,
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )


def a_working_morning(runner: CliRunner, tmp_path: Path) -> Path:
    """Everything up to a drawn syringe, through the commands."""
    bookfile = a_book(runner, tmp_path)
    a_customer(runner, bookfile)
    a_physician(runner, bookfile)
    an_order(runner, bookfile)
    a_bench(runner, bookfile)
    a_released_batch(runner, bookfile)
    a_calibrator(bookfile)
    a_drawn_dose(runner, bookfile)
    return bookfile
