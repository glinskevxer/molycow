import datetime as dt

import pytest
from tests.conftest import at
from tests.support import a_register

from molycow.errors import RuleError, ValidationError
from molycow.formulary import formula
from molycow.model import Customer, CustomerKind
from molycow.service.orders import OrderService
from molycow.store import Book
from molycow.store.orders import OrderRepository
from molycow.store.register import AuthorizedUserRepository, CustomerRepository
from molycow.units import Activity

ORDERED = at("2025-04-07 16:10")
CALIBRATION = at("2025-04-08 08:00")


def take(service: OrderService, **changed: object) -> object:
    fields: dict[str, object] = {
        "customer_id": "CU-0001",
        "user_id": "AU-0004",
        "code": "MDP",
        "procedure": "whole body bone",
        "patient_ref": "A-4471902",
        "activity": Activity.of(22, "mci"),
        "calibration_at": CALIBRATION,
        "ordered_at": ORDERED,
    }
    fields.update(changed)
    return service.take(**fields)  # type: ignore[arg-type]


def test_an_order_is_numbered_for_the_day_it_was_taken(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    first = take(service)
    assert first.id == "ORD-250407-01"  # type: ignore[attr-defined]
    assert OrderRepository(book).count() == 1


def test_the_usual_adult_dose_range_comes_from_the_monograph() -> None:
    assert formula("MDP").dose_fits(Activity.of(22, "mci"))
    assert not formula("MDP").dose_fits(Activity.of(2, "mci"))
    with pytest.raises(ValidationError, match="not an adult dose"):
        formula("MAA").check_dose(Activity.of(20, "mci"))


def test_a_dose_outside_the_usual_range_is_refused(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    with pytest.raises(RuleError, match="not an adult dose"):
        take(service, activity=Activity.of(120, "mci"))


def test_a_customer_that_is_shut_that_day_is_refused(book: Book) -> None:
    a_register(book, closed_on=dt.date(2025, 3, 31))
    service = OrderService(book)
    with pytest.raises(RuleError, match="not on the books"):
        take(service)


def test_a_clinic_cannot_order_therapy(book: Book) -> None:
    a_register(book, kind=CustomerKind.CLINIC)
    AuthorizedUserRepository(book).set_nuclides("AU-0004", ["Tc-99m", "I-131"])
    service = OrderService(book)
    refused = service.refusal_for("CU-0001", "AU-0004", "MDP", Activity.of(22, "mci"), CALIBRATION)
    assert refused is None


def test_a_physician_from_another_hospital_is_refused(book: Book) -> None:
    a_register(book)
    CustomerRepository(book).add(
        Customer(
            id="CU-0002",
            name="Halvern Clinic",
            kind=CustomerKind.CLINIC,
            licence="42-28931-02",
            street="9 Depot Road",
            town="Ardmore",
            zone="river",
            opened_on=dt.date(2025, 1, 6),
        )
    )
    service = OrderService(book)
    with pytest.raises(RuleError, match="not named at that customer"):
        take(service, customer_id="CU-0002")


def test_a_physician_who_has_left_is_refused(book: Book) -> None:
    a_register(book)
    AuthorizedUserRepository(book).end("AU-0004", dt.date(2025, 3, 1))
    service = OrderService(book)
    with pytest.raises(RuleError, match="not current that day"):
        take(service)


def test_a_physician_not_named_for_the_nuclide_is_refused(book: Book) -> None:
    a_register(book)
    AuthorizedUserRepository(book).set_nuclides("AU-0004", ["I-131"])
    service = OrderService(book)
    with pytest.raises(RuleError, match="not named for that nuclide"):
        take(service)


def test_a_refused_order_is_not_written_down(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    with pytest.raises(RuleError):
        take(service, activity=Activity.of(120, "mci"))
    assert OrderRepository(book).count() == 0


def test_an_order_can_be_cancelled_once(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    order = take(service)
    cancelled = service.cancel(order.id)  # type: ignore[attr-defined]
    assert not cancelled.is_open()
    with pytest.raises(RuleError, match="already been finished"):
        service.cancel(order.id)  # type: ignore[attr-defined]


def test_the_worklist_is_the_next_few_hours(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    soon = take(service)
    take(service, calibration_at=at("2025-04-08 15:00"))
    worklist = service.worklist(at("2025-04-08 06:30"), hours=4)
    assert [one.id for one in worklist] == [soon.id]  # type: ignore[attr-defined]
    assert len(service.worklist(at("2025-04-08 06:30"), hours=12)) == 2


def test_the_days_orders_are_the_open_ones_calibrated_that_day(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    first = take(service)
    take(service, calibration_at=at("2025-04-08 15:00"))
    service.cancel(first.id)  # type: ignore[attr-defined]
    assert len(service.due_on(dt.date(2025, 4, 8))) == 1


def test_an_order_still_open_after_its_time_shows_as_late(book: Book) -> None:
    a_register(book)
    service = OrderService(book)
    order = take(service)
    assert service.late(at("2025-04-08 07:00")) == []
    assert [one.id for one in service.late(at("2025-04-08 09:00"))] == [order.id]  # type: ignore[attr-defined]
