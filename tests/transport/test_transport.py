from decimal import Decimal

import pytest

from molycow.errors import ValidationError
from molycow.transport import (
    METRE_LIMIT_MREM,
    SURFACE_LIMIT_MREM,
    Label,
    a2_fraction,
    a2_quantity,
    fits_in_a_van,
    fits_type_a,
    label_for,
    transport_index,
    vehicle_index,
)
from molycow.units import Activity


def test_the_transport_index_rounds_up_never_down() -> None:
    assert transport_index(Decimal("0.41")) == Decimal("0.5")
    assert transport_index(Decimal("0.40")) == Decimal("0.4")
    assert transport_index(Decimal("1.001")) == Decimal("1.1")
    assert transport_index(Decimal(0)) == Decimal(0)


def test_a_negative_reading_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        transport_index(Decimal("-0.1"))
    with pytest.raises(ValidationError, match="cannot be negative"):
        label_for(Decimal("-1"), Decimal(0))


def test_a_quiet_package_takes_the_white_label() -> None:
    assert label_for(Decimal("0.3"), Decimal(0)) is Label.WHITE_I
    assert not Label.WHITE_I.needs_index_on_the_label


def test_a_package_reading_at_the_surface_takes_yellow_two() -> None:
    assert label_for(Decimal("0.8"), Decimal(0)) is Label.YELLOW_II
    assert label_for(Decimal(40), Decimal("0.9")) is Label.YELLOW_II
    assert Label.YELLOW_II.needs_index_on_the_label


def test_a_busy_package_takes_yellow_three() -> None:
    assert label_for(Decimal(60), Decimal("0.4")) is Label.YELLOW_III
    assert label_for(Decimal(30), Decimal("1.4")) is Label.YELLOW_III


def test_a_package_over_the_surface_limit_cannot_ship() -> None:
    with pytest.raises(ValidationError, match="over the surface limit"):
        label_for(SURFACE_LIMIT_MREM + Decimal(1), Decimal(1))


def test_a_package_over_the_index_limit_cannot_ship() -> None:
    with pytest.raises(ValidationError, match="over the transport index limit"):
        label_for(Decimal(30), METRE_LIMIT_MREM + Decimal(1))


def test_the_a2_quantity_comes_off_the_table() -> None:
    assert a2_quantity("Tc-99m") == Activity.of("10.8", "ci")
    assert a2_quantity("i131") == Activity.of("0.7", "ci")


def test_a_nuclide_with_no_a2_on_file_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not handle"):
        a2_quantity("Pu-239")


def test_the_a2_fraction_is_what_the_package_is_carrying() -> None:
    fraction = a2_fraction("Tc-99m", Activity.of("5.4", "ci"))
    assert fraction == Decimal("0.5")
    assert fits_type_a("Tc-99m", Activity.of(2, "ci"))


def test_a_therapy_dose_fills_far_more_of_its_a2_than_a_scan_dose() -> None:
    therapy = a2_fraction("I-131", Activity.of(200, "mci"))
    scan = a2_fraction("Tc-99m", Activity.of(200, "mci"))
    assert therapy > scan
    assert fits_type_a("I-131", Activity.of(200, "mci"))
    assert not fits_type_a("I-131", Activity.of(1, "ci"))


def test_the_indexes_on_a_truck_add_up() -> None:
    assert vehicle_index([Decimal("0.4"), Decimal("1.2"), Decimal("0.1")]) == Decimal("1.7")
    assert vehicle_index([]) == Decimal("0.0")
    assert fits_in_a_van([Decimal(20), Decimal(20)])
    assert not fits_in_a_van([Decimal(30), Decimal(30)])
