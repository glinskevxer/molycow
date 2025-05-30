from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.order import MAX_LEAD_HOURS, Order, OrderState
from molycow.units import Activity

ORDERED = at("2025-04-07 16:10")
CALIBRATION = at("2025-04-08 08:00")


def an_order(**changed: object) -> Order:
    fields: dict[str, object] = {
        "id": "ORD-250407-11",
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
    return Order(**fields)  # type: ignore[arg-type]


def test_an_order_names_a_kit_and_the_nuclide_follows() -> None:
    order = an_order()
    assert order.code == "MDP"
    assert order.nuclide == "Tc-99m"
    assert order.formula.rcp_floor == Decimal(90)


def test_an_order_needs_a_procedure_and_a_reference() -> None:
    with pytest.raises(ValidationError, match="the procedure it is for"):
        an_order(procedure="  ")
    with pytest.raises(ValidationError, match="department's reference"):
        an_order(patient_ref="")


def test_an_order_for_nothing_is_not_an_order() -> None:
    with pytest.raises(ValidationError, match="not an order"):
        an_order(activity=Activity.zero())


def test_a_calibration_time_in_the_past_is_refused() -> None:
    with pytest.raises(ValidationError, match="already gone by"):
        an_order(calibration_at=at("2025-04-07 09:00"))


def test_a_calibration_time_too_far_out_is_refused() -> None:
    with pytest.raises(ValidationError, match="too far out"):
        an_order(calibration_at=at("2025-04-11 09:00"))
    assert Decimal(72) == MAX_LEAD_HOURS


def test_the_notice_the_pharmacy_was_given() -> None:
    assert an_order().lead_hours.quantize(Decimal("0.001")) == Decimal("15.833")
    assert an_order().hours_to_calibration(at("2025-04-08 06:00")) == Decimal(2)


def test_an_order_is_open_until_it_is_finished() -> None:
    order = an_order()
    assert order.is_open()
    assert not order.state.is_final
    assert order.filled().state is OrderState.FILLED
    assert order.cancelled().state is OrderState.CANCELLED
    assert order.filled().state.is_final


def test_an_order_cannot_be_finished_twice() -> None:
    filled = an_order().filled()
    with pytest.raises(ValidationError, match="already been finished"):
        filled.cancelled()


def test_an_order_is_late_once_its_calibration_time_goes_by() -> None:
    order = an_order()
    assert not order.is_late_at(at("2025-04-08 07:00"))
    assert order.is_late_at(at("2025-04-08 09:00"))
    assert not order.filled().is_late_at(at("2025-04-08 09:00"))


def test_the_ids_have_to_be_the_right_kinds() -> None:
    with pytest.raises(ValidationError, match="wrong kind of number"):
        an_order(customer_id="AU-0004")
    with pytest.raises(ValidationError, match="wrong kind of number"):
        an_order(user_id="CU-0001")
    with pytest.raises(ValidationError, match="wrong kind of number"):
        an_order(id="B-250407-11")


def test_a_kit_the_pharmacy_does_not_compound_is_refused_on_an_order() -> None:
    with pytest.raises(ValidationError, match="does not compound"):
        an_order(code="HIDA")
