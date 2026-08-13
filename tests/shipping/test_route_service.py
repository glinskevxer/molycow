import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_customer, a_working_day, an_order

from molycow.errors import NotFoundError, RuleError
from molycow.model.route import Route
from molycow.service.dispense import DispenseService
from molycow.service.route import RouteService
from molycow.service.shipping import ShippingService
from molycow.store import Book
from molycow.store.routes import RouteRepository

DAY = dt.date(2025, 4, 8)
DRAW = at("2025-04-08 07:40")
PACK = at("2025-04-08 08:20")


def a_box(book: Book, order_id: str | None = None) -> str:
    day = a_working_day(book)
    dispensing = DispenseService(book)
    wanted = order_id or day.order_id
    planned = dispensing.plan(wanted, day.batch_id, DRAW)
    dose = dispensing.draw(
        wanted, day.batch_id, DRAW, planned.needed, "K. Ruzicka", day.calibrator_id
    )
    box = ShippingService(book).pack(
        "CU-0001", [dose.id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35")
    )
    return box.id


def two_boxes(book: Book) -> tuple[str, str]:
    """Two boxes for the same customer, off one working day."""
    day = a_working_day(book)
    second = an_order(book, "ORD-250407-12", patient_ref="A-4471903")
    dispensing = DispenseService(book)
    shipping = ShippingService(book)
    packed = []
    for order_id in (day.order_id, second.id):
        planned = dispensing.plan(order_id, day.batch_id, DRAW)
        dose = dispensing.draw(
            order_id, day.batch_id, DRAW, planned.needed, "K. Ruzicka", day.calibrator_id
        )
        box = shipping.pack(
            "CU-0001", [dose.id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35")
        )
        packed.append(box.id)
    return packed[0], packed[1]


def a_route(book: Book, route_id: str = "RT-0001", **changed: object) -> Route:
    fields: dict[str, object] = {
        "id": route_id,
        "name": f"north morning {route_id[-4:]}",
        "zone": "north",
        "stops": ("CU-0001",),
        "leaves_at": dt.time(6, 30),
    }
    fields.update(changed)
    return RouteRepository(book).add(Route(**fields))  # type: ignore[arg-type]


def test_a_box_goes_on_the_run_that_calls_at_its_customer(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    load = service.load("RT-0001", DAY, box_id)
    assert [one.id for one in load.shipments] == [box_id]
    assert load.index == Decimal("0.4")
    assert load.stops_with_boxes == ["CU-0001"]


def test_a_box_for_a_customer_the_run_does_not_call_at_is_refused(book: Book) -> None:
    box_id = a_box(book)
    a_customer(book, id="CU-0002", name="Halvern Clinic", zone="river")
    a_route(book, "RT-0002", zone="river", stops=("CU-0002",))
    service = RouteService(book)
    service.open_run("RT-0002", DAY, "J. Fennimore")
    with pytest.raises(RuleError, match="does not call at that customer"):
        service.load("RT-0002", DAY, box_id)


def test_a_box_can_only_be_on_one_run(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    a_route(book, "RT-0002")
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.open_run("RT-0002", DAY, "P. Vantrease")
    service.load("RT-0001", DAY, box_id)
    with pytest.raises(RuleError, match="already on a run"):
        service.load("RT-0002", DAY, box_id)


def test_the_boxes_waiting_for_a_run(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    service = RouteService(book)
    assert [one.id for one in service.waiting_for("RT-0001")] == [box_id]
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.load("RT-0001", DAY, box_id)
    assert service.waiting_for("RT-0001") == []


def test_an_empty_van_does_not_leave(book: Book) -> None:
    a_customer(book)
    a_route(book)
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    with pytest.raises(RuleError, match="nothing on that run"):
        service.depart("RT-0001", DAY, at("2025-04-08 08:40"))


def test_a_loaded_van_leaves_and_comes_back(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.load("RT-0001", DAY, box_id)
    run = service.depart("RT-0001", DAY, at("2025-04-08 08:40"))
    assert run.has_left
    service.deliver("RT-0001", DAY, box_id, at("2025-04-08 09:05"), "Reception")
    back = service.arrive_back("RT-0001", DAY, at("2025-04-08 09:50"))
    assert back.is_back
    assert service.load_of("RT-0001", DAY).undelivered() == []


def test_nothing_is_loaded_after_the_van_has_gone(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.load("RT-0001", DAY, box_id)
    service.depart("RT-0001", DAY, at("2025-04-08 08:40"))
    with pytest.raises(RuleError, match="already left"):
        service.load("RT-0001", DAY, box_id)


def test_a_box_cannot_be_delivered_before_the_van_leaves(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.load("RT-0001", DAY, box_id)
    with pytest.raises(RuleError, match="has not left yet"):
        service.deliver("RT-0001", DAY, box_id, at("2025-04-08 08:00"), "Reception")


def test_a_box_on_another_run_cannot_be_signed_off_this_one(book: Book) -> None:
    first, second = two_boxes(book)
    a_route(book)
    a_route(book, "RT-0002")
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.open_run("RT-0002", DAY, "P. Vantrease")
    service.load("RT-0001", DAY, first)
    service.load("RT-0002", DAY, second)
    service.depart("RT-0001", DAY, at("2025-04-08 08:40"))
    service.depart("RT-0002", DAY, at("2025-04-08 08:45"))
    with pytest.raises(RuleError, match="not on that run"):
        service.deliver("RT-0002", DAY, first, at("2025-04-08 09:05"), "Reception")


def test_the_days_runs_come_back_together(book: Book) -> None:
    box_id = a_box(book)
    a_route(book)
    service = RouteService(book)
    service.open_run("RT-0001", DAY, "J. Fennimore")
    service.load("RT-0001", DAY, box_id)
    runs = service.runs_on(DAY)
    assert len(runs) == 1
    assert runs[0].route.id == "RT-0001"
    assert service.runs_on(dt.date(2025, 4, 9)) == []


def test_a_run_that_was_never_opened(book: Book) -> None:
    a_customer(book)
    a_route(book)
    service = RouteService(book)
    with pytest.raises(NotFoundError, match="no such run"):
        service.load_of("RT-0001", DAY)
