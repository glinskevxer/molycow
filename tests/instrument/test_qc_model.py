import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.qc import (
    CheckKind,
    LinearityPoint,
    LinearityRun,
    QcCheck,
    deviation,
)
from molycow.units import Activity

RUN_AT = at("2025-04-08 06:15")


def a_check(**changed: object) -> QcCheck:
    fields: dict[str, object] = {
        "instrument_id": "IC-0003",
        "kind": CheckKind.CONSTANCY,
        "at": RUN_AT,
        "source_serial": "CS-9912",
        "expected": Activity.of(163, "uci"),
        "measured": Activity.of(159, "uci"),
        "checked_by": "K. Ruzicka",
    }
    fields.update(changed)
    return QcCheck(**fields)  # type: ignore[arg-type]


def a_run(**changed: object) -> LinearityRun:
    points = (
        LinearityPoint(at("2025-04-08 07:00"), Activity.of(400, "mci")),
        LinearityPoint(at("2025-04-08 13:00"), Activity.of("200.1", "mci")),
        LinearityPoint(at("2025-04-09 07:00"), Activity.of("25.2", "mci")),
        LinearityPoint(at("2025-04-10 07:00"), Activity.of("1.58", "mci")),
    )
    fields: dict[str, object] = {
        "instrument_id": "IC-0003",
        "symbol": "Tc-99m",
        "points": points,
        "checked_by": "K. Ruzicka",
    }
    fields.update(changed)
    return LinearityRun(**fields)  # type: ignore[arg-type]


def test_each_check_has_its_own_tolerance() -> None:
    assert CheckKind.CONSTANCY.tolerance_percent == Decimal(10)
    assert CheckKind.ACCURACY.tolerance_percent == Decimal(5)
    assert CheckKind.LINEARITY.tolerance_percent == Decimal(5)
    assert CheckKind.GEOMETRY.tolerance_percent == Decimal(2)


def test_each_check_comes_round_at_its_own_interval() -> None:
    assert CheckKind.CONSTANCY.interval_days == 1
    assert CheckKind.LINEARITY.interval_days == 92
    assert CheckKind.GEOMETRY.interval_days is None


def test_a_deviation_is_signed_and_to_a_tenth() -> None:
    assert deviation(Activity.of(159, "uci"), Activity.of(163, "uci")) == Decimal("-2.5")
    assert deviation(Activity.of(170, "uci"), Activity.of(163, "uci")) == Decimal("4.3")


def test_a_reading_cannot_be_compared_against_nothing() -> None:
    with pytest.raises(ValidationError, match="against nothing"):
        deviation(Activity.of(1, "uci"), Activity.zero())


def test_a_constancy_check_inside_ten_percent_passes() -> None:
    check = a_check()
    assert check.passes
    assert check.note() == "constancy passed at -2.5%"


def test_the_same_reading_fails_the_tighter_accuracy_tolerance() -> None:
    loose = a_check(measured=Activity.of(152, "uci"))
    tight = a_check(kind=CheckKind.ACCURACY, measured=Activity.of(152, "uci"))
    assert loose.passes
    assert not tight.passes
    assert tight.note().startswith("accuracy FAILED")


def test_a_daily_check_comes_round_tomorrow() -> None:
    assert a_check().due_again() == dt.date(2025, 4, 9)
    assert a_check(kind=CheckKind.LINEARITY).due_again() == dt.date(2025, 7, 9)
    assert a_check(kind=CheckKind.GEOMETRY).due_again() is None


def test_a_check_names_its_source_and_is_signed() -> None:
    with pytest.raises(ValidationError, match="names the source"):
        a_check(source_serial=" ")
    with pytest.raises(ValidationError, match="is signed"):
        a_check(checked_by="")
    with pytest.raises(ValidationError, match="measured nothing"):
        a_check(measured=Activity.zero())


def test_a_linearity_run_measures_each_point_against_the_first() -> None:
    run = a_run()
    assert run.deviations()[0] == Decimal("0.0")
    assert run.passes()
    assert abs(run.worst) < Decimal(5)
    assert run.lowest() == Activity.of("1.58", "mci")


def test_a_calibrator_that_reads_low_at_the_bottom_fails_linearity() -> None:
    points = (
        LinearityPoint(at("2025-04-08 07:00"), Activity.of(400, "mci")),
        LinearityPoint(at("2025-04-08 13:00"), Activity.of("200.1", "mci")),
        LinearityPoint(at("2025-04-09 07:00"), Activity.of("25.2", "mci")),
        LinearityPoint(at("2025-04-10 07:00"), Activity.of("1.35", "mci")),
    )
    run = a_run(points=points)
    assert not run.passes()
    assert run.worst < Decimal(-5)


def test_a_linearity_run_covers_the_days_it_was_read_over() -> None:
    assert a_run().hours_covered == Decimal(48)


def test_a_run_of_two_readings_is_not_a_run() -> None:
    with pytest.raises(ValidationError, match="at least three readings"):
        a_run(
            points=(
                LinearityPoint(at("2025-04-08 07:00"), Activity.of(400, "mci")),
                LinearityPoint(at("2025-04-08 13:00"), Activity.of(200, "mci")),
            )
        )


def test_a_run_read_out_of_order_is_refused() -> None:
    points = (
        LinearityPoint(at("2025-04-09 07:00"), Activity.of(25, "mci")),
        LinearityPoint(at("2025-04-08 07:00"), Activity.of(400, "mci")),
        LinearityPoint(at("2025-04-10 07:00"), Activity.of("1.5", "mci")),
    )
    with pytest.raises(ValidationError, match="in the order it was read"):
        a_run(points=points)


def test_a_run_that_starts_from_nothing_is_refused() -> None:
    points = (
        LinearityPoint(at("2025-04-08 07:00"), Activity.zero()),
        LinearityPoint(at("2025-04-08 13:00"), Activity.of(200, "mci")),
        LinearityPoint(at("2025-04-09 07:00"), Activity.of(25, "mci")),
    )
    with pytest.raises(ValidationError, match="cannot start from nothing"):
        a_run(points=points)
