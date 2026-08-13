import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_working_day, an_order

from molycow.errors import RuleError
from molycow.service.dispense import DispenseService
from molycow.service.shipping import ShippingService
from molycow.store import Book

DRAW = at("2025-04-08 07:40")
PACK = at("2025-04-08 08:20")


def a_dose(book: Book, order_id: str | None = None) -> str:
    day = a_working_day(book)
    service = DispenseService(book)
    wanted = order_id or day.order_id
    planned = service.plan(wanted, day.batch_id, DRAW)
    dose = service.draw(wanted, day.batch_id, DRAW, planned.needed, "K. Ruzicka", day.calibrator_id)
    return dose.id


def test_a_drawn_dose_is_ready_to_pack(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    assert service.ready_for("CU-0001", PACK) == [dose_id]


def test_packing_closes_the_box_and_reads_it(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    box = service.pack("CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))
    assert box.id == "SH-250408-01"
    assert box.dose_count == 1
    assert box.transport_index == Decimal("0.4")
    assert service.ready_for("CU-0001", PACK) == []


def test_the_activity_on_the_box_is_the_activity_at_packing(book: Book) -> None:
    """Not the sum of the labels, which are calibrated for a later moment."""
    from molycow.store.doses import DoseRepository

    dose_id = a_dose(book)
    dose = DoseRepository(book).get(dose_id)
    box = ShippingService(book).pack(
        "CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35")
    )
    assert box.activity == dose.activity_at(PACK)
    assert box.activity < dose.assayed
    assert box.activity > dose.at_calibration


def test_an_empty_box_is_refused(book: Book) -> None:
    a_dose(book)
    service = ShippingService(book)
    with pytest.raises(RuleError, match="nothing to pack"):
        service.pack("CU-0001", [], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))


def test_a_dose_cannot_be_packed_twice(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    service.pack("CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))
    with pytest.raises(RuleError, match="already in a box"):
        service.pack("CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))


def test_a_dose_for_another_customer_cannot_go_in_this_box(book: Book) -> None:
    dose_id = a_dose(book)
    from molycow.model import Customer, CustomerKind
    from molycow.store.register import CustomerRepository

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
    service = ShippingService(book)
    with pytest.raises(RuleError, match="another customer"):
        service.pack("CU-0002", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))


def test_a_box_cannot_be_packed_before_the_dose_was_drawn(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    with pytest.raises(RuleError, match="had not been drawn yet"):
        service.pack(
            "CU-0001",
            [dose_id],
            at("2025-04-08 07:00"),
            "K. Ruzicka",
            Decimal("12"),
            Decimal("0.35"),
        )


def test_a_box_over_the_surface_limit_cannot_be_closed(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    with pytest.raises(Exception, match="over the surface limit"):
        service.pack("CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal(400), Decimal("0.35"))


def test_two_doses_for_the_same_customer_go_in_one_box(book: Book) -> None:
    day = a_working_day(book)
    second = an_order(book, "ORD-250407-12", patient_ref="A-4471903")
    service = DispenseService(book)
    first_plan = service.plan(day.order_id, day.batch_id, DRAW)
    first = service.draw(
        day.order_id, day.batch_id, DRAW, first_plan.needed, "K. Ruzicka", day.calibrator_id
    )
    second_plan = service.plan(second.id, day.batch_id, DRAW)
    other = service.draw(
        second.id, day.batch_id, DRAW, second_plan.needed, "K. Ruzicka", day.calibrator_id
    )
    shipping = ShippingService(book)
    box = shipping.pack(
        "CU-0001", [first.id, other.id], PACK, "K. Ruzicka", Decimal("18"), Decimal("0.6")
    )
    assert box.dose_count == 2
    assert box.activity > first.activity_at(PACK)


def test_the_manifest_adds_the_indexes_up(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    service.pack("CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))
    manifest = service.manifest(dt.date(2025, 4, 8))
    assert manifest.dose_count == 1
    assert manifest.vehicle_index == Decimal("0.4")
    assert manifest.lines()[0].startswith("SH-250408-01 CU-0001")


def test_a_box_stays_outstanding_until_it_is_signed_for(book: Book) -> None:
    dose_id = a_dose(book)
    service = ShippingService(book)
    box = service.pack("CU-0001", [dose_id], PACK, "K. Ruzicka", Decimal("12"), Decimal("0.35"))
    assert [one.id for one in service.outstanding()] == [box.id]
    service.deliver(box.id, at("2025-04-08 09:05"), "J. Fennimore")
    assert service.outstanding() == []
