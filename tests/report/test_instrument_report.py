import datetime as dt
from decimal import Decimal

from tests.conftest import at
from tests.support import a_calibrator

from molycow.model.qc import CheckKind
from molycow.report.instruments import instrument_sheet
from molycow.service.qc import QcService
from molycow.store import Book
from molycow.store.instruments import CheckSourceRepository

DAY = dt.date(2025, 4, 8)


def test_a_lab_with_nothing_in_it_says_so(book: Book) -> None:
    sheet = instrument_sheet(book, DAY)
    assert sheet.section("instruments").is_empty
    assert sheet.section("sources").is_empty
    assert sheet.section("failed checks").is_empty


def test_an_instrument_shows_its_due_date_and_its_last_check(book: Book) -> None:
    a_calibrator(book)
    row = instrument_sheet(book, DAY).section("instruments").rows[0]
    assert "IC-0003" in row
    assert "calibration due 2026-02-03" in row
    assert "last constancy 2025-04-08 06:05" in row
    assert "in service" in row


def test_an_unchecked_instrument_says_never_checked(book: Book) -> None:
    a_calibrator(book, checked=False)
    row = instrument_sheet(book, DAY).section("instruments").rows[0]
    assert "never checked" in row
    assert "constancy overdue" in instrument_sheet(book, DAY).section("overdue").rows[0]


def test_an_instrument_out_of_calibration_says_why(book: Book) -> None:
    a_calibrator(book)
    row = instrument_sheet(book, dt.date(2026, 6, 1)).section("instruments").rows[0]
    assert "annual calibration has run out" in row


def test_a_failed_check_is_on_the_board(book: Book) -> None:
    a_calibrator(book, checked=False)
    source = CheckSourceRepository(book).get("CS-9912")
    QcService(book).run(
        "IC-0003",
        CheckKind.CONSTANCY,
        "CS-9912",
        at("2025-04-08 06:05"),
        source.activity_on(DAY).scaled(Decimal("0.5")),
        "K. Ruzicka",
    )
    rows = instrument_sheet(book, DAY).section("failed checks").rows
    assert "constancy FAILED" in rows[0]


def test_the_sources_show_what_they_read_today(book: Book) -> None:
    a_calibrator(book)
    row = instrument_sheet(book, DAY).section("sources").rows[0]
    assert row.startswith("CS-9912")
    assert "reads" in row


def test_a_checked_instrument_drops_constancy_off_the_overdue_list(book: Book) -> None:
    a_calibrator(book)
    overdue = instrument_sheet(book, DAY).section("overdue").rows
    assert not any("constancy" in row for row in overdue)
    assert any("linearity" in row for row in overdue)
