from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.dose import TOLERANCE_PERCENT, Dose
from molycow.units import Activity, Volume

DRAWN = at("2025-04-08 07:40")
CALIBRATION = at("2025-04-08 09:00")


def a_dose(**changed: object) -> Dose:
    fields: dict[str, object] = {
        "id": "DS-250408-14",
        "order_id": "ORD-250407-11",
        "batch_id": "B-250408-01",
        "code": "MDP",
        "drawn_at": DRAWN,
        "calibration_at": CALIBRATION,
        "volume": Volume.of("0.55"),
        "assayed": Activity.of("24.6", "mci"),
        "drawn_by": "K. Ruzicka",
    }
    fields.update(changed)
    return Dose(**fields)  # type: ignore[arg-type]


def test_a_dose_decays_from_the_assay_to_the_calibration_time() -> None:
    dose = a_dose()
    assert dose.at_calibration.format("mci", 2) == "21.09 mCi"
    assert dose.hours_held().quantize(Decimal("0.01")) == Decimal("1.33")


def test_a_dose_drawn_at_its_calibration_time_reads_the_assay() -> None:
    dose = a_dose(calibration_at=DRAWN)
    assert dose.at_calibration == dose.assayed


def test_a_dose_has_no_activity_before_it_was_drawn() -> None:
    with pytest.raises(ValidationError, match="before it was drawn"):
        a_dose().activity_at(at("2025-04-08 07:00"))


def test_a_dose_cannot_be_calibrated_for_a_moment_before_it_was_drawn() -> None:
    with pytest.raises(ValidationError, match="before it was drawn"):
        a_dose(calibration_at=at("2025-04-08 07:00"))


def test_the_variance_is_measured_at_the_calibration_time() -> None:
    dose = a_dose()
    assert dose.variance_from(Activity.of(22, "mci")) == Decimal("-4.1")
    assert dose.within_tolerance(Activity.of(22, "mci"))


def test_a_dose_well_over_the_order_is_out_of_tolerance() -> None:
    dose = a_dose(assayed=Activity.of(30, "mci"))
    assert dose.variance_from(Activity.of(22, "mci")) == Decimal("16.9")
    assert not dose.within_tolerance(Activity.of(22, "mci"))


def test_a_dose_well_under_the_order_is_out_of_tolerance() -> None:
    dose = a_dose(assayed=Activity.of(18, "mci"))
    assert dose.variance_from(Activity.of(22, "mci")) == Decimal("-29.8")
    assert not dose.within_tolerance(Activity.of(22, "mci"))


def test_the_tolerance_can_be_tightened_for_a_fussy_department() -> None:
    dose = a_dose(assayed=Activity.of("26", "mci"))
    assert dose.within_tolerance(Activity.of(22, "mci"))
    assert not dose.within_tolerance(Activity.of(22, "mci"), tolerance=Decimal(1))
    assert Decimal(10) == TOLERANCE_PERCENT


def test_a_dose_cannot_be_compared_against_nothing() -> None:
    with pytest.raises(ValidationError, match="against no order"):
        a_dose().variance_from(Activity.zero())


def test_an_empty_syringe_is_not_a_dose() -> None:
    with pytest.raises(ValidationError, match="nothing in it"):
        a_dose(volume=Volume.zero())
    with pytest.raises(ValidationError, match="assay above zero"):
        a_dose(assayed=Activity.zero())


def test_a_dose_is_signed() -> None:
    with pytest.raises(ValidationError, match="signed by"):
        a_dose(drawn_by="")


def test_the_label_carries_the_order_activity_and_the_clock_time() -> None:
    assert a_dose().label(Activity.of(22, "mci")) == (
        "DS-250408-14 Tc-99m medronate 22.0 mCi at 0900"
    )


def test_the_ids_have_to_be_the_right_kinds() -> None:
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_dose(order_id="B-250408-01")
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_dose(batch_id="ORD-250407-11")
