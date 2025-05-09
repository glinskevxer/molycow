from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.purity import PurityTest, Strip, System

TESTED = at("2025-04-08 07:35")


def a_test(**changed: object) -> PurityTest:
    fields: dict[str, object] = {
        "batch_id": "B-250408-01",
        "tested_at": TESTED,
        "solvent": Strip(System.SOLVENT, origin=48200, front=1100),
        "saline": Strip(System.SALINE, origin=900, front=47600),
        "tested_by": "K. Ruzicka",
    }
    fields.update(changed)
    return PurityTest(**fields)  # type: ignore[arg-type]


def test_each_system_looks_for_its_own_impurity() -> None:
    assert System.SOLVENT.impurity == "free pertechnetate"
    assert System.SALINE.impurity == "hydrolysed reduced technetium"


def test_the_solvent_strip_reads_what_ran_with_the_front() -> None:
    strip = Strip(System.SOLVENT, origin=9000, front=1000)
    assert strip.impurity_percent == Decimal("10.0")


def test_the_saline_strip_reads_what_stayed_at_the_origin() -> None:
    strip = Strip(System.SALINE, origin=500, front=9500)
    assert strip.impurity_percent == Decimal("5.0")


def test_background_comes_off_before_anything_is_divided() -> None:
    plain = Strip(System.SOLVENT, origin=9000, front=1000)
    with_background = Strip(System.SOLVENT, origin=9200, front=1200, background=200)
    assert with_background.impurity_percent == plain.impurity_percent
    assert with_background.net_total == 10000


def test_a_count_under_background_reads_as_nothing() -> None:
    strip = Strip(System.SOLVENT, origin=9000, front=40, background=100)
    assert strip.net_front == 0
    assert strip.impurity_percent == Decimal("0.0")


def test_a_negative_count_is_refused_by_part() -> None:
    with pytest.raises(ValidationError) as caught:
        Strip(System.SOLVENT, origin=-1, front=10)
    assert caught.value.detail["part"] == "origin"


def test_a_strip_that_counted_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="nothing above background"):
        Strip(System.SALINE, origin=100, front=100, background=500)


def test_the_purity_is_what_is_left_after_both_impurities() -> None:
    reading = a_test()
    assert reading.free_percent == Decimal("2.2")
    assert reading.hydrolysed_percent == Decimal("1.9")
    assert reading.rcp == Decimal("95.9")


def test_a_clean_batch_passes_the_floor_and_a_dirty_one_does_not() -> None:
    assert a_test().passes(Decimal(90))
    dirty = a_test(solvent=Strip(System.SOLVENT, origin=40000, front=9000))
    assert dirty.free_percent == Decimal("18.4")
    assert not dirty.passes(Decimal(90))


def test_two_bad_strips_cannot_take_the_purity_below_zero() -> None:
    awful = a_test(
        solvent=Strip(System.SOLVENT, origin=1000, front=9000),
        saline=Strip(System.SALINE, origin=9000, front=1000),
    )
    assert awful.rcp == Decimal("0.0")


def test_the_log_names_the_bigger_impurity() -> None:
    assert a_test().worst_impurity() == "free pertechnetate"
    hydrolysed = a_test(saline=Strip(System.SALINE, origin=8000, front=42000))
    assert hydrolysed.worst_impurity() == "hydrolysed reduced technetium"


def test_the_strips_cannot_be_swapped_into_the_wrong_slots() -> None:
    with pytest.raises(ValidationError, match="solvent strip is in the wrong slot"):
        a_test(solvent=Strip(System.SALINE, origin=100, front=900))
    with pytest.raises(ValidationError, match="saline strip is in the wrong slot"):
        a_test(saline=Strip(System.SOLVENT, origin=100, front=900))


def test_a_purity_test_belongs_to_a_batch_and_is_signed() -> None:
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_test(batch_id="EL-250408-01")
    with pytest.raises(ValidationError, match="is signed"):
        a_test(tested_by=" ")
