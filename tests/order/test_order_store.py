import datetime as dt

import pytest
from tests.conftest import at

from molycow.errors import NotFoundError
from molycow.model import AuthorizedUser, Customer, CustomerKind
from molycow.model.order import Order, OrderState
from molycow.store import Book
from molycow.store.orders import OrderRepository
from molycow.store.register import AuthorizedUserRepository, CustomerRepository
from molycow.units import Activity

ORDERED = at("2025-04-07 16:10")


def a_register(book: Book) -> None:
    CustomerRepository(book).add(
        Customer(
            id="CU-0001",
            name="Saint Brannon Medical Centre",
            kind=CustomerKind.HOSPITAL,
            licence="42-28931-01",
            street="1400 Weir Street",
            town="Ardmore",
            zone="north",
            opened_on=dt.date(2025, 1, 6),
        )
    )
    AuthorizedUserRepository(book).add(
        AuthorizedUser(
            id="AU-0004",
            customer_id="CU-0001",
            name="R. Okonkwo",
            licence="42-28931-01",
            added_on=dt.date(2025, 1, 6),
            nuclides=frozenset({"Tc-99m"}),
        )
    )


def an_order(order_id: str = "ORD-250407-11", **changed: object) -> Order:
    fields: dict[str, object] = {
        "id": order_id,
        "customer_id": "CU-0001",
        "user_id": "AU-0004",
        "code": "MDP",
        "procedure": "whole body bone",
        "patient_ref": "A-4471902",
        "activity": Activity.of(22, "mci"),
        "calibration_at": at("2025-04-08 08:00"),
        "ordered_at": ORDERED,
    }
    fields.update(changed)
    return Order(**fields)  # type: ignore[arg-type]


def test_an_order_goes_in_and_comes_back_the_same(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    repo.add(an_order())
    assert repo.get("ORD-250407-11") == an_order()


def test_an_order_needs_a_customer_and_a_user_that_exist(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        OrderRepository(book).add(an_order())


def test_an_order_that_is_not_there(book: Book) -> None:
    repo = OrderRepository(book)
    assert repo.find("ORD-250407-99") is None
    with pytest.raises(NotFoundError, match="no such order"):
        repo.get("ORD-250407-99")


def test_orders_come_back_in_calibration_order(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    repo.add(an_order("ORD-250407-12", calibration_at=at("2025-04-08 13:00")))
    repo.add(an_order("ORD-250407-11"))
    assert [one.id for one in repo.all()] == ["ORD-250407-11", "ORD-250407-12"]


def test_a_state_change_is_written_back(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    order = repo.add(an_order())
    repo.save_state(order.filled())
    assert repo.get(order.id).state is OrderState.FILLED
    assert repo.open_orders() == []
    assert repo.count(OrderState.FILLED) == 1
    assert repo.count() == 1


def test_open_orders_are_the_ones_still_to_do(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    first = repo.add(an_order())
    repo.add(an_order("ORD-250407-12", calibration_at=at("2025-04-08 13:00")))
    repo.save_state(first.cancelled())
    assert [one.id for one in repo.open_orders()] == ["ORD-250407-12"]


def test_orders_for_one_customer_can_be_filtered_by_state(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    first = repo.add(an_order())
    repo.add(an_order("ORD-250407-12", calibration_at=at("2025-04-08 13:00")))
    repo.save_state(first.filled())
    assert len(repo.for_customer("CU-0001")) == 2
    filled = repo.for_customer("CU-0001", state=OrderState.FILLED)
    assert [one.id for one in filled] == ["ORD-250407-11"]


def test_the_orders_due_on_a_day_are_the_ones_calibrated_that_day(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    repo.add(an_order())
    repo.add(an_order("ORD-250407-12", calibration_at=at("2025-04-09 08:00")))
    assert [one.id for one in repo.due_on(dt.date(2025, 4, 8))] == ["ORD-250407-11"]
    assert [one.id for one in repo.due_on(dt.date(2025, 4, 9))] == ["ORD-250407-12"]


def test_orders_due_in_a_window(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    repo.add(an_order())
    repo.add(an_order("ORD-250407-12", calibration_at=at("2025-04-08 13:00")))
    window = repo.due_between(at("2025-04-08 07:00"), at("2025-04-08 09:00"))
    assert [one.id for one in window] == ["ORD-250407-11"]


def test_an_order_still_open_after_its_calibration_time_is_late(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    order = repo.add(an_order())
    assert repo.late_at(at("2025-04-08 07:00")) == []
    assert [one.id for one in repo.late_at(at("2025-04-08 09:00"))] == [order.id]
    repo.save_state(order.filled())
    assert repo.late_at(at("2025-04-08 09:00")) == []


def test_the_next_order_number_restarts_each_morning(book: Book) -> None:
    a_register(book)
    repo = OrderRepository(book)
    assert repo.next_id(dt.date(2025, 4, 7)) == "ORD-250407-01"
    repo.add(an_order())
    assert repo.next_id(dt.date(2025, 4, 7)) == "ORD-250407-12"
    assert repo.next_id(dt.date(2025, 4, 8)) == "ORD-250408-01"
