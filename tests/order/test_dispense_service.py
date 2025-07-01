import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.order.test_dose_store import a_day

from molycow.errors import ReleaseError, RuleError
from molycow.model.purity import Strip, System
from molycow.service.dispense import DispenseService
from molycow.service.purity import PurityService
from molycow.store import Book
from molycow.store.orders import OrderRepository
from molycow.units import Activity, Volume

DRAW = at("2025-04-08 07:40")
CLEAN_SOLVENT = Strip(System.SOLVENT, origin=48200, front=1100)
CLEAN_SALINE = Strip(System.SALINE, origin=900, front=47600)


def a_released_batch(book: Book) -> str:
    batch_id = a_day(book)
    PurityService(book).run(
        batch_id, at("2025-04-08 07:30"), CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka"
    )
    return batch_id


def test_the_plan_pulls_more_than_the_order_asks_for(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    assert planned.needed > planned.order.activity
    assert planned.volume.ml > Decimal(0)
    assert planned.label_activity.format() == "22.000 mCi"


def test_a_later_draw_is_the_same_volume_and_a_smaller_activity(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    early = service.plan("ORD-250407-11", batch_id, at("2025-04-08 07:35"))
    late = service.plan("ORD-250407-11", batch_id, at("2025-04-08 08:35"))
    assert late.needed < early.needed
    assert late.volume == early.volume


def test_drawing_fills_the_syringe_and_closes_the_order(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    dose = service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka")
    assert dose.id == "DS-250408-01"
    assert dose.within_tolerance(Activity.of(22, "mci"))
    assert not OrderRepository(book).get("ORD-250407-11").is_open()
    assert service.for_order("ORD-250407-11") == dose


def test_a_syringe_that_assays_light_goes_back(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    with pytest.raises(ReleaseError, match="does not assay close enough"):
        service.draw("ORD-250407-11", batch_id, DRAW, Activity.of(15, "mci"), "K. Ruzicka")
    assert OrderRepository(book).get("ORD-250407-11").is_open()
    assert service.for_order("ORD-250407-11") is None


def test_a_tight_tolerance_can_be_asked_for(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    slightly_over = planned.needed.scaled(Decimal("1.05"))
    service.draw("ORD-250407-11", batch_id, DRAW, slightly_over, "K. Ruzicka", tolerance=Decimal(6))
    assert service.for_order("ORD-250407-11") is not None


def test_an_order_cannot_be_filled_twice(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka")
    with pytest.raises(RuleError, match="not open"):
        service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka")


def test_a_held_batch_cannot_be_drawn_from(book: Book) -> None:
    batch_id = a_day(book)
    service = DispenseService(book)
    with pytest.raises(ReleaseError, match="no purity reading yet"):
        service.plan("ORD-250407-11", batch_id, DRAW)


def test_a_draw_after_the_calibration_time_is_refused(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    with pytest.raises(RuleError, match="already gone by"):
        service.plan("ORD-250407-11", batch_id, at("2025-04-08 09:30"))


def test_what_is_left_in_the_batch_goes_down(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    before = service.remaining_in(batch_id)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    dose = service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka")
    assert service.drawn_from(batch_id) == dose.volume
    assert service.remaining_in(batch_id) == before - dose.volume


def test_a_draw_bigger_than_the_batch_is_refused(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    with pytest.raises(RuleError, match="not enough left"):
        service.draw(
            "ORD-250407-11",
            batch_id,
            DRAW,
            planned.needed,
            "K. Ruzicka",
            volume=Volume.of(9),
        )


def test_the_bench_can_ask_which_batches_would_do(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    assert [one.id for one in service.batches_for("ORD-250407-11", DRAW)] == [batch_id]
    assert service.batches_for("ORD-250407-11", at("2025-04-08 09:30")) == []


def test_the_days_doses_come_back_together(book: Book) -> None:
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka")
    assert len(service.drawn_on(dt.date(2025, 4, 8))) == 1
    assert service.drawn_on(dt.date(2025, 4, 9)) == []
