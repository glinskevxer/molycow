from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_working_day, an_order

from molycow.errors import NotFoundError
from molycow.report.period import month
from molycow.report.statement import statement
from molycow.service.dispense import DispenseService
from molycow.service.orders import OrderService
from molycow.service.returns import ReturnService
from molycow.service.shipping import ShippingService
from molycow.store import Book

APRIL = month(2025, 4)


def a_filled_order(book: Book) -> str:
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


def test_a_customer_with_nothing_ordered_reads_empty(book: Book) -> None:
    from tests.support import a_register

    a_register(book)
    sheet = statement(book, "CU-0001", APRIL)
    assert sheet.section("orders").is_empty
    assert sheet.section("summary").rows[0] == "0 orders"


def test_a_filled_order_is_counted_and_totalled(book: Book) -> None:
    a_filled_order(book)
    sheet = statement(book, "CU-0001", APRIL)
    summary = sheet.section("summary").rows
    assert summary[0] == "1 orders"
    assert "1 filled" in summary[1]
    assert "100.0% of the orders were filled" in summary[-1]


def test_the_order_row_carries_both_activities(book: Book) -> None:
    a_filled_order(book)
    row = statement(book, "CU-0001", APRIL).section("orders").rows[0]
    assert "A-4471902" in row
    assert "ordered" in row
    assert "drawn" in row
    assert "filled" in row


def test_an_order_nobody_filled_is_named(book: Book) -> None:
    a_working_day(book)
    sheet = statement(book, "CU-0001", APRIL)
    assert sheet.section("not filled").rows == ("ORD-250407-11",)
    assert "1 not filled" in sheet.section("summary").rows[2]


def test_a_cancelled_order_is_not_counted_as_unfilled(book: Book) -> None:
    a_working_day(book)
    OrderService(book).cancel("ORD-250407-11")
    sheet = statement(book, "CU-0001", APRIL)
    assert sheet.section("not filled").is_empty
    assert "1 cancelled" in sheet.section("summary").rows[3]


def test_a_returned_dose_reads_as_returned(book: Book) -> None:
    dose_id = a_filled_order(book)
    shipping = ShippingService(book)
    box = shipping.pack(
        "CU-0001", [dose_id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    shipping.deliver(box.id, at("2025-04-08 09:05"), "Reception")
    ReturnService(book).take_back(dose_id, at("2025-04-08 15:30"), "not attended", "K. R")
    sheet = statement(book, "CU-0001", APRIL)
    assert sheet.section("orders").rows[0].endswith("returned")
    assert "1 came back" in sheet.section("summary").rows[4]


def test_another_month_holds_none_of_it(book: Book) -> None:
    a_filled_order(book)
    sheet = statement(book, "CU-0001", month(2025, 5))
    assert sheet.section("orders").is_empty


def test_a_second_order_shows_on_the_same_statement(book: Book) -> None:
    a_filled_order(book)
    an_order(book, "ORD-250407-12", patient_ref="A-4471903")
    sheet = statement(book, "CU-0001", APRIL)
    assert len(sheet.section("orders").rows) == 2
    assert "50.0% of the orders were filled" in sheet.section("summary").rows[-1]


def test_a_customer_that_is_not_there(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no such customer"):
        statement(book, "CU-0404", APRIL)
