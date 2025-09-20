import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_working_day

from molycow.errors import ConflictError, NotFoundError
from molycow.model.shipment import Shipment
from molycow.service.dispense import DispenseService
from molycow.store import Book
from molycow.store.shipments import ShipmentRepository
from molycow.units import Activity

PACKED = at("2025-04-08 08:20")


def a_dose(book: Book) -> str:
    day = a_working_day(book)
    service = DispenseService(book)
    planned = service.plan(day.order_id, day.batch_id, at("2025-04-08 07:40"))
    dose = service.draw(
        day.order_id,
        day.batch_id,
        at("2025-04-08 07:40"),
        planned.needed,
        "K. Ruzicka",
        day.calibrator_id,
    )
    return dose.id


def a_shipment(dose_id: str, shipment_id: str = "SH-250408-03", **changed: object) -> Shipment:
    fields: dict[str, object] = {
        "id": shipment_id,
        "customer_id": "CU-0001",
        "packed_at": PACKED,
        "packed_by": "K. Ruzicka",
        "dose_ids": (dose_id,),
        "symbol": "Tc-99m",
        "activity": Activity.of(24, "mci"),
        "surface_mrem": Decimal("12"),
        "metre_mrem": Decimal("0.35"),
    }
    fields.update(changed)
    return Shipment(**fields)  # type: ignore[arg-type]


def test_a_shipment_goes_in_and_comes_back_whole(book: Book) -> None:
    dose_id = a_dose(book)
    repo = ShipmentRepository(book)
    repo.add(a_shipment(dose_id))
    back = repo.get("SH-250408-03")
    assert back.dose_ids == (dose_id,)
    assert back.surface_mrem == Decimal("12")
    assert not back.is_delivered


def test_a_shipment_needs_doses_that_exist(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        ShipmentRepository(book).add(a_shipment("DS-250408-99"))


def test_a_dose_can_only_be_in_one_box(book: Book) -> None:
    dose_id = a_dose(book)
    repo = ShipmentRepository(book)
    repo.add(a_shipment(dose_id))
    with pytest.raises(ConflictError):
        repo.add(a_shipment(dose_id, "SH-250408-04"))


def test_the_box_holding_a_dose_can_be_found(book: Book) -> None:
    dose_id = a_dose(book)
    repo = ShipmentRepository(book)
    repo.add(a_shipment(dose_id))
    holding = repo.holding(dose_id)
    assert holding is not None
    assert holding.id == "SH-250408-03"
    assert repo.holding("DS-250408-99") is None


def test_signing_for_a_box_closes_it(book: Book) -> None:
    dose_id = a_dose(book)
    repo = ShipmentRepository(book)
    repo.add(a_shipment(dose_id))
    signed = repo.sign_for("SH-250408-03", at("2025-04-08 09:05"), "J. Fennimore")
    assert signed.is_delivered
    assert repo.get("SH-250408-03").received_by == "J. Fennimore"
    assert repo.undelivered() == []


def test_boxes_come_back_by_customer_and_by_day(book: Book) -> None:
    dose_id = a_dose(book)
    repo = ShipmentRepository(book)
    repo.add(a_shipment(dose_id))
    assert [one.id for one in repo.for_customer("CU-0001")] == ["SH-250408-03"]
    assert [one.id for one in repo.on_day(dt.date(2025, 4, 8))] == ["SH-250408-03"]
    assert repo.on_day(dt.date(2025, 4, 9)) == []


def test_the_next_shipment_number_restarts_each_morning(book: Book) -> None:
    dose_id = a_dose(book)
    repo = ShipmentRepository(book)
    assert repo.next_id(dt.date(2025, 4, 8)) == "SH-250408-01"
    repo.add(a_shipment(dose_id))
    assert repo.next_id(dt.date(2025, 4, 8)) == "SH-250408-04"


def test_a_shipment_that_is_not_there(book: Book) -> None:
    repo = ShipmentRepository(book)
    assert repo.find("SH-250408-09") is None
    with pytest.raises(NotFoundError, match="no such shipment"):
        repo.get("SH-250408-09")
