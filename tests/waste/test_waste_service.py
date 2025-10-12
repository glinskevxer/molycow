from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_working_day

from molycow.errors import RuleError, SafetyError
from molycow.model.waste import ContainerKind
from molycow.service.dispense import DispenseService
from molycow.service.waste import BACKGROUND_MREM, WasteService
from molycow.store import Book
from molycow.units import Activity

OPENED = at("2025-04-08 06:00")
DISCARDED = at("2025-04-08 10:30")


def a_drum(book: Book) -> str:
    service = WasteService(book)
    return service.open_container(ContainerKind.VIALS, OPENED).id


def test_a_drum_is_opened_and_numbered(book: Book) -> None:
    service = WasteService(book)
    drum = service.open_container(ContainerKind.VIALS, OPENED)
    assert drum.id == "WC-0001"
    assert not drum.is_closed


def test_things_go_in_while_it_is_open(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "Tc-99m", Activity.of(40, "mci"), DISCARDED, "EL-250408-01")
    filled = service.discard(drum_id, "Tc-99m", Activity.of(8, "mci"), DISCARDED, "B-250408-01")
    assert len(filled.items) == 2
    assert service.activity_in_store(DISCARDED).format() == "48.000 mCi"


def test_nothing_goes_in_before_the_drum_was_opened(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    with pytest.raises(RuleError, match="had not been opened yet"):
        service.discard(
            drum_id, "Tc-99m", Activity.of(40, "mci"), at("2025-04-07 09:00"), "EL-250407-01"
        )


def test_nothing_goes_in_once_it_is_closed(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "Tc-99m", Activity.of(40, "mci"), DISCARDED, "EL-250408-01")
    service.close(drum_id, at("2025-04-08 17:00"))
    with pytest.raises(RuleError, match="that container is closed"):
        service.discard(drum_id, "Tc-99m", Activity.of(4, "mci"), at("2025-04-08 18:00"), "X")


def test_an_unused_syringe_goes_in_at_what_it_reads_now(book: Book) -> None:
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
    service = WasteService(book)
    drum_id = service.open_container(ContainerKind.SHARPS, OPENED).id
    filled = service.discard_dose(drum_id, dose.id, at("2025-04-08 16:00"))
    assert filled.items[0].source == dose.id
    assert filled.items[0].activity < dose.assayed


def test_a_drum_is_held_until_the_hold_and_the_survey_both_pass(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "Tc-99m", Activity.of(40, "mci"), DISCARDED, "EL-250408-01")
    with pytest.raises(RuleError, match="still open"):
        service.dispose(drum_id, at("2025-04-20 09:00"), "K. Ruzicka", Decimal("0.01"))
    service.close(drum_id, at("2025-04-08 17:00"))
    with pytest.raises(RuleError, match="not held ten half lives"):
        service.dispose(drum_id, at("2025-04-09 09:00"), "K. Ruzicka", Decimal("0.01"))
    gone = service.dispose(drum_id, at("2025-04-12 09:00"), "K. Ruzicka", Decimal("0.01"))
    assert gone.is_disposed


def test_a_drum_that_still_reads_above_background_stays(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "Tc-99m", Activity.of(40, "mci"), DISCARDED, "EL-250408-01")
    service.close(drum_id, at("2025-04-08 17:00"))
    with pytest.raises(SafetyError, match="does not survey at background"):
        service.dispose(
            drum_id, at("2025-04-12 09:00"), "K. Ruzicka", BACKGROUND_MREM + Decimal("0.01")
        )
    assert service.ready(at("2025-04-12 09:00")) != []


def test_a_drum_cannot_go_out_twice(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "Tc-99m", Activity.of(40, "mci"), DISCARDED, "EL-250408-01")
    service.close(drum_id, at("2025-04-08 17:00"))
    service.dispose(drum_id, at("2025-04-12 09:00"), "K. Ruzicka", Decimal("0.01"))
    with pytest.raises(RuleError, match="already gone"):
        service.dispose(drum_id, at("2025-04-13 09:00"), "K. Ruzicka", Decimal("0.01"))


def test_the_store_says_what_is_holding_and_why(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "I-131", Activity.of(5, "mci"), DISCARDED, "DS-250408-20")
    service.close(drum_id, at("2025-04-08 17:00"))
    held = service.held(at("2025-04-12 09:00"))
    assert [one.note() for one in held] == ["WC-0001 not held ten half lives yet"]
    assert service.ready(at("2025-04-12 09:00")) == []
    assert service.ready(at("2026-01-12 09:00"))[0].id == drum_id


def test_the_open_container_of_a_kind_is_reused(book: Book) -> None:
    service = WasteService(book)
    first = service.container_for(ContainerKind.SHARPS, OPENED)
    again = service.container_for(ContainerKind.SHARPS, OPENED)
    assert first.id == again.id
    other = service.container_for(ContainerKind.LIQUID, OPENED)
    assert other.id != first.id


def test_a_disposed_drum_stops_counting_in_the_store(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.discard(drum_id, "Tc-99m", Activity.of(40, "mci"), DISCARDED, "EL-250408-01")
    service.close(drum_id, at("2025-04-08 17:00"))
    service.dispose(drum_id, at("2025-04-12 09:00"), "K. Ruzicka", Decimal("0.01"))
    assert service.activity_in_store(at("2025-04-12 09:00")).is_zero()
    assert service.held(at("2025-04-12 09:00")) == []
