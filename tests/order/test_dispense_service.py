import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_batch, a_calibrator, a_register, a_released_batch, an_order

from molycow.errors import ReleaseError, RuleError, SafetyError
from molycow.service.dispense import DispenseService
from molycow.store import Book
from molycow.store.orders import OrderRepository
from molycow.units import Activity, Volume

DRAW = at("2025-04-08 07:40")


def a_day(book: Book) -> str:
    a_register(book)
    an_order(book)
    a_calibrator(book)
    return a_batch(book)


def a_bench_with_a_released_batch(book: Book) -> str:
    a_register(book)
    an_order(book)
    a_calibrator(book)
    return a_released_batch(book)


def test_the_plan_pulls_more_than_the_order_asks_for(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    assert planned.needed > planned.order.activity
    assert planned.volume.ml > Decimal(0)
    assert planned.label_activity.format() == "22.000 mCi"


def test_a_later_draw_is_the_same_volume_and_a_smaller_activity(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    early = service.plan("ORD-250407-11", batch_id, at("2025-04-08 07:35"))
    late = service.plan("ORD-250407-11", batch_id, at("2025-04-08 08:35"))
    assert late.needed < early.needed
    assert late.volume == early.volume


def test_drawing_fills_the_syringe_and_closes_the_order(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    dose = service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0003")
    assert dose.id == "DS-250408-01"
    assert dose.within_tolerance(Activity.of(22, "mci"))
    assert not OrderRepository(book).get("ORD-250407-11").is_open()
    assert service.for_order("ORD-250407-11") == dose


def test_a_syringe_that_assays_light_goes_back(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    with pytest.raises(ReleaseError, match="does not assay close enough"):
        service.draw(
            "ORD-250407-11", batch_id, DRAW, Activity.of(15, "mci"), "K. Ruzicka", "IC-0003"
        )
    assert OrderRepository(book).get("ORD-250407-11").is_open()
    assert service.for_order("ORD-250407-11") is None


def test_a_tight_tolerance_can_be_asked_for(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    slightly_over = planned.needed.scaled(Decimal("1.05"))
    service.draw(
        "ORD-250407-11",
        batch_id,
        DRAW,
        slightly_over,
        "K. Ruzicka",
        "IC-0003",
        tolerance=Decimal(6),
    )
    assert service.for_order("ORD-250407-11") is not None


def test_an_order_cannot_be_filled_twice(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0003")
    with pytest.raises(RuleError, match="not open"):
        service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0003")


def test_a_held_batch_cannot_be_drawn_from(book: Book) -> None:
    batch_id = a_day(book)
    service = DispenseService(book)
    with pytest.raises(ReleaseError, match="no purity reading yet"):
        service.plan("ORD-250407-11", batch_id, DRAW)


def test_a_draw_after_the_calibration_time_is_refused(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    with pytest.raises(RuleError, match="already gone by"):
        service.plan("ORD-250407-11", batch_id, at("2025-04-08 09:30"))


def test_what_is_left_in_the_batch_goes_down(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    before = service.remaining_in(batch_id)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    dose = service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0003")
    assert service.drawn_from(batch_id) == dose.volume
    assert service.remaining_in(batch_id) == before - dose.volume


def test_a_draw_bigger_than_the_batch_is_refused(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    with pytest.raises(RuleError, match="not enough left"):
        service.draw(
            "ORD-250407-11",
            batch_id,
            DRAW,
            planned.needed,
            "K. Ruzicka",
            "IC-0003",
            volume=Volume.of(9),
        )


def test_the_bench_can_ask_which_batches_would_do(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    assert [one.id for one in service.batches_for("ORD-250407-11", DRAW)] == [batch_id]
    assert service.batches_for("ORD-250407-11", at("2025-04-08 09:30")) == []


def test_the_days_doses_come_back_together(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0003")
    assert len(service.drawn_on(dt.date(2025, 4, 8))) == 1
    assert service.drawn_on(dt.date(2025, 4, 9)) == []


def test_the_calibrator_that_read_the_syringe_is_named_on_the_dose(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    dose = service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0003")
    assert dose.calibrator_id == "IC-0003"


def test_a_calibrator_with_no_morning_check_stops_the_draw(book: Book) -> None:
    a_register(book)
    an_order(book)
    a_calibrator(book, "IC-0009", checked=False)
    batch_id = a_released_batch(book)
    service = DispenseService(book)
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    with pytest.raises(SafetyError, match="not passed its constancy check today"):
        service.draw("ORD-250407-11", batch_id, DRAW, planned.needed, "K. Ruzicka", "IC-0009")
    assert OrderRepository(book).get("ORD-250407-11").is_open()


def test_a_draw_too_small_to_measure_is_refused(book: Book) -> None:
    from tests.support import (
        CLEAN_SALINE,
        CLEAN_SOLVENT,
        a_calibrator,
        a_kit_lot,
        an_elution,
    )

    from molycow.service.compound import CompoundService
    from molycow.service.purity import PurityService

    a_register(book)
    order = an_order(
        book,
        "ORD-250407-20",
        code="SC",
        procedure="sentinel node",
        activity=Activity.of("0.5", "mci"),
    )
    a_calibrator(book)
    elution_id = an_elution(book)
    a_kit_lot(book, "KL-0200", code="SC")
    colloid = CompoundService(book).compound(
        "SC",
        elution_id,
        at("2025-04-08 07:15"),
        Activity.of(80, "mci"),
        "K. Ruzicka",
        volume=Volume.of(1),
    )
    PurityService(book).run(
        colloid.id, at("2025-04-08 07:30"), CLEAN_SOLVENT, CLEAN_SALINE, "K. Ruzicka"
    )
    service = DispenseService(book)
    with pytest.raises(RuleError, match="too small to draw"):
        service.plan(order.id, colloid.id, DRAW)


def test_the_floor_under_a_draw_is_fifty_microlitres() -> None:
    from molycow.service.dispense import SMALLEST_DRAW

    assert Volume.of("0.05") == SMALLEST_DRAW


def test_the_bench_says_the_smallest_dose_a_batch_can_give(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    smallest = service.smallest_from(batch_id, DRAW)
    assert smallest > Activity.zero()
    planned = service.plan("ORD-250407-11", batch_id, DRAW)
    assert planned.needed > smallest


def test_the_smallest_dose_falls_with_the_batch(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    early = service.smallest_from(batch_id, at("2025-04-08 07:40"))
    late = service.smallest_from(batch_id, at("2025-04-08 11:40"))
    assert late < early


def test_the_bench_can_be_told_what_to_dilute_to(book: Book) -> None:
    batch_id = a_bench_with_a_released_batch(book)
    service = DispenseService(book)
    wanted = Activity.of("1", "mci")
    made_up = service.dilution_for(batch_id, wanted, DRAW)
    assert made_up > Volume.of("3.4")
    with pytest.raises(RuleError, match="nothing is not an activity"):
        service.dilution_for(batch_id, Activity.zero(), DRAW)


def test_a_rule_exists_for_a_draw_that_is_too_small() -> None:
    from molycow.rules import find

    rule = find("draw-volume")
    assert rule is not None
    assert rule.about == "doses"
