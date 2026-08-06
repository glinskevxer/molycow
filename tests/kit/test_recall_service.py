import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_kit_lot, a_working_day

from molycow.errors import ValidationError
from molycow.service.dispense import DispenseService
from molycow.service.recall import RecallService
from molycow.service.shipping import ShippingService
from molycow.store import Book
from molycow.store.audit import AuditRepository
from molycow.store.kits import KitLotRepository

PULLED = at("2025-04-10 09:00")


def a_dose(book: Book) -> str:
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


def test_a_lot_that_touched_nothing_reaches_nothing(book: Book) -> None:
    a_kit_lot(book)
    reach = RecallService(book).reach_of("KL-0114")
    assert reach.is_empty
    assert reach.lines() == ["KL-0114 MDP lot 9F0114"]


def test_a_recall_walks_forward_to_the_hospital(book: Book) -> None:
    dose_id = a_dose(book)
    service = RecallService(book)
    reach = service.recall("KL-0114", PULLED, "maker found particulates", "K. Ruzicka")
    assert [one.id for one in reach.batches] == ["B-250408-01"]
    assert reach.dose_ids == (dose_id,)
    assert reach.customers == ("CU-0001",)
    assert any(line.startswith("  telephone Saint Brannon") for line in reach.lines())


def test_a_recall_finds_the_box_the_dose_went_out_in(book: Book) -> None:
    dose_id = a_dose(book)
    ShippingService(book).pack(
        "CU-0001", [dose_id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    reach = RecallService(book).reach_of("KL-0114")
    assert reach.shipments == ("SH-250408-01",)


def test_a_recalled_lot_comes_off_the_shelf(book: Book) -> None:
    a_kit_lot(book)
    service = RecallService(book)
    service.recall("KL-0114", PULLED, "maker found particulates", "K. Ruzicka")
    lots = KitLotRepository(book)
    assert lots.get("KL-0114").is_recalled
    assert lots.oldest_in_date("MDP", dt.date(2025, 4, 11)) is None
    assert [one.id for one in service.recalled_lots()] == ["KL-0114"]


def test_a_recall_is_written_into_the_trail(book: Book) -> None:
    a_kit_lot(book)
    RecallService(book).recall("KL-0114", PULLED, "maker found particulates", "K. Ruzicka")
    trail = AuditRepository(book).for_subject("KL-0114")
    assert trail[0].action == "amended"
    assert "particulates" in trail[0].detail


def test_a_lot_is_recalled_once_and_says_why(book: Book) -> None:
    a_kit_lot(book)
    service = RecallService(book)
    service.recall("KL-0114", PULLED, "maker found particulates", "K. Ruzicka")
    with pytest.raises(ValidationError, match="already been recalled"):
        service.recall("KL-0114", PULLED, "again", "K. Ruzicka")
    a_kit_lot(book, "KL-0115")
    with pytest.raises(ValidationError, match="recall says why"):
        service.recall("KL-0115", PULLED, "  ", "K. Ruzicka")


def test_the_batches_from_every_pulled_lot_come_back_together(book: Book) -> None:
    a_dose(book)
    service = RecallService(book)
    assert service.batches_from_recalled() == []
    service.recall("KL-0114", PULLED, "maker found particulates", "K. Ruzicka")
    assert [one.id for one in service.batches_from_recalled()] == ["B-250408-01"]


def test_the_recall_list_carries_the_telephone_number(book: Book) -> None:
    from molycow.store.register import CustomerRepository

    a_dose(book)
    customer = CustomerRepository(book).get("CU-0001")
    book.execute("UPDATE customer SET telephone = ? WHERE id = ?", ("580 555 0148", customer.id))
    reach = RecallService(book).reach_of("KL-0114")
    assert reach.telephone == ("Saint Brannon Medical Centre (nuclear medicine) on 580 555 0148",)
    assert any("580 555 0148" in line for line in reach.lines())


def test_a_customer_with_no_number_still_appears_on_the_list(book: Book) -> None:
    a_dose(book)
    reach = RecallService(book).reach_of("KL-0114")
    assert any("no telephone on file" in line for line in reach.lines())
