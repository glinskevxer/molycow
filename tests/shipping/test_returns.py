from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_working_day

from molycow.errors import NotFoundError, RuleError
from molycow.service.dispense import DispenseService
from molycow.service.returns import ReturnService
from molycow.service.shipping import ShippingService
from molycow.store import Book
from molycow.store.audit import AuditRepository
from molycow.store.waste import ContainerRepository

BACK = at("2025-04-08 15:30")


def a_delivered_dose(book: Book) -> str:
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
    shipping = ShippingService(book)
    box = shipping.pack(
        "CU-0001", [dose.id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    shipping.deliver(box.id, at("2025-04-08 09:05"), "Reception")
    return dose.id


def test_a_syringe_comes_back_at_what_it_reads_now(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    came_back = ReturnService(book).take_back(dose_id, BACK, "patient did not attend", "K. R")
    assert came_back.activity_back < came_back.dose.assayed
    assert "patient did not attend" in came_back.line()


def test_a_returned_syringe_goes_into_a_sharps_container(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    came_back = ReturnService(book).take_back(dose_id, BACK, "patient did not attend", "K. R")
    assert came_back.container_id is not None
    container = ContainerRepository(book).get(came_back.container_id)
    assert container.items[0].source == dose_id
    assert container.kind.value == "sharps"


def test_a_dose_that_never_left_cannot_come_back(book: Book) -> None:
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
    with pytest.raises(RuleError, match="never left the building"):
        ReturnService(book).take_back(dose.id, BACK, "not used", "K. R")


def test_a_return_says_why_and_happens_once(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    service = ReturnService(book)
    with pytest.raises(RuleError, match="says why"):
        service.take_back(dose_id, BACK, "  ", "K. R")
    service.take_back(dose_id, BACK, "patient did not attend", "K. R")
    with pytest.raises(RuleError, match="already back"):
        service.take_back(dose_id, BACK, "again", "K. R")


def test_a_return_before_the_dose_was_drawn_is_refused(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    with pytest.raises(RuleError, match="had not been drawn"):
        ReturnService(book).take_back(dose_id, at("2025-04-08 07:00"), "not used", "K. R")


def test_the_returns_are_listed_by_customer(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    service = ReturnService(book)
    assert service.all() == []
    service.take_back(dose_id, BACK, "patient did not attend", "K. R")
    assert [one.dose.id for one in service.for_customer("CU-0001")] == [dose_id]
    assert service.for_customer("CU-0002") == []


def test_what_the_returns_are_worth_falls_through_the_afternoon(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    service = ReturnService(book)
    service.take_back(dose_id, BACK, "patient did not attend", "K. R")
    early = service.unused_activity(BACK)
    late = service.unused_activity(at("2025-04-08 19:30"))
    assert late < early


def test_a_return_is_written_into_the_trail(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    ReturnService(book).take_back(dose_id, BACK, "patient did not attend", "K. R")
    trail = AuditRepository(book).for_subject(dose_id)
    assert trail[-1].action == "discarded"
    assert "returned" in trail[-1].detail


def test_a_dose_that_has_not_come_back(book: Book) -> None:
    dose_id = a_delivered_dose(book)
    service = ReturnService(book)
    assert service.find(dose_id) is None
    with pytest.raises(NotFoundError, match="has not come back"):
        service.get(dose_id)


def test_the_returns_table_keeps_what_it_was_told(book: Book) -> None:
    from molycow.store.returns import ReturnRepository

    dose_id = a_delivered_dose(book)
    ReturnService(book).take_back(dose_id, BACK, "patient did not attend", "K. Ruzicka")
    repo = ReturnRepository(book)
    assert repo.count() == 1
    record = repo.get(dose_id)
    assert record.received_by == "K. Ruzicka"
    assert record.container_id is not None


def test_a_return_record_says_why_and_who_signed(book: Book) -> None:
    from molycow.errors import ValidationError
    from molycow.model.dose import DoseReturn

    with pytest.raises(ValidationError, match="says why"):
        DoseReturn("DS-250408-01", BACK, " ", "K. R")
    with pytest.raises(ValidationError, match="signed for"):
        DoseReturn("DS-250408-01", BACK, "not used", " ")
    with pytest.raises(ValidationError, match="wrong kind of number"):
        DoseReturn("B-250408-01", BACK, "not used", "K. R")
