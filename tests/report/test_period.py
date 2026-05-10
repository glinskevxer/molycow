import datetime as dt
from decimal import Decimal

from tests.conftest import at
from tests.support import a_working_day

from molycow.report.period import midnight_after, month, month_of, period_sheet
from molycow.service.dispense import DispenseService
from molycow.store import Book

APRIL = month(2025, 4)


def a_day_of_work(book: Book) -> str:
    day = a_working_day(book)
    dispensing = DispenseService(book)
    planned = dispensing.plan(day.order_id, day.batch_id, at("2025-04-08 07:40"))
    dose = dispensing.draw(
        day.order_id,
        day.batch_id,
        at("2025-04-08 07:40"),
        planned.needed,
        "K. Ruzicka",
        day.calibrator_id,
    )
    return dose.id


def test_a_month_runs_from_the_first_to_the_last() -> None:
    assert APRIL.first == dt.date(2025, 4, 1)
    assert APRIL.last == dt.date(2025, 4, 30)
    assert APRIL.days == 30
    assert str(APRIL) == "2025-04-01 to 2025-04-30"


def test_december_ends_on_the_thirty_first() -> None:
    assert month(2025, 12).last == dt.date(2025, 12, 31)
    assert month(2024, 2).days == 29


def test_a_day_knows_the_month_it_falls_in() -> None:
    assert month_of(dt.date(2025, 4, 8)) == APRIL
    assert APRIL.holds(dt.date(2025, 4, 8))
    assert not APRIL.holds(dt.date(2025, 5, 1))


def test_an_empty_period_still_counts_its_days(book: Book) -> None:
    sheet = period_sheet(book, APRIL)
    assert sheet.section("work").rows[1] == "0 elutions"
    assert sheet.section("column yields").lines()[1] == "  no column was milked"
    assert sheet.section("customers").is_empty
    assert sheet.section("returns").is_empty


def test_the_work_section_counts_the_month(book: Book) -> None:
    a_day_of_work(book)
    rows = period_sheet(book, APRIL).section("work").rows
    assert "30 days" in rows[0]
    assert "1 elutions" in rows[1]
    assert "1 batches" in rows[2]
    assert "1 doses" in rows[3]
    assert "went into a syringe" in rows[4]


def test_the_share_that_went_into_a_syringe_is_small_on_one_dose(book: Book) -> None:
    a_day_of_work(book)
    used = period_sheet(book, APRIL).section("work").rows[4]
    assert used.split("%")[0].replace(".", "").isdigit()
    assert Decimal(used.split("%")[0]) < Decimal(20)


def test_the_yields_section_names_the_worst_column(book: Book) -> None:
    a_day_of_work(book)
    rows = period_sheet(book, APRIL).section("column yields").rows
    assert rows[0].startswith("average yield")
    assert "EL-250408-01" in rows[1]


def test_the_customers_section_adds_up_per_hospital(book: Book) -> None:
    a_day_of_work(book)
    rows = period_sheet(book, APRIL).section("customers").rows
    assert rows[0].startswith("CU-0001")
    assert "1 doses" in rows[0]


def test_a_month_with_nothing_in_it_reads_empty(book: Book) -> None:
    a_day_of_work(book)
    sheet = period_sheet(book, month(2025, 5))
    assert sheet.section("customers").is_empty


def test_a_returned_dose_shows_in_the_period(book: Book) -> None:
    from molycow.service.returns import ReturnService
    from molycow.service.shipping import ShippingService

    dose_id = a_day_of_work(book)
    shipping = ShippingService(book)
    box = shipping.pack(
        "CU-0001", [dose_id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    shipping.deliver(box.id, at("2025-04-08 09:05"), "Reception")
    ReturnService(book).take_back(dose_id, at("2025-04-08 15:30"), "not attended", "K. R")
    rows = period_sheet(book, APRIL).section("returns").rows
    assert rows[0].startswith(dose_id)


def test_the_end_of_the_period_is_a_moment(book: Book) -> None:
    end = midnight_after(APRIL)
    assert end.date() == dt.date(2025, 4, 30)
    assert end.hour == 23
