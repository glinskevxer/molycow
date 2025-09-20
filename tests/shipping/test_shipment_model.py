from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.shipment import Shipment
from molycow.transport import Label
from molycow.units import Activity

PACKED = at("2025-04-08 08:20")


def a_shipment(**changed: object) -> Shipment:
    fields: dict[str, object] = {
        "id": "SH-250408-03",
        "customer_id": "CU-0001",
        "packed_at": PACKED,
        "packed_by": "K. Ruzicka",
        "dose_ids": ("DS-250408-14", "DS-250408-15"),
        "symbol": "Tc-99m",
        "activity": Activity.of(48, "mci"),
        "surface_mrem": Decimal("12"),
        "metre_mrem": Decimal("0.35"),
    }
    fields.update(changed)
    return Shipment(**fields)  # type: ignore[arg-type]


def test_a_package_carries_its_label_and_its_index() -> None:
    box = a_shipment()
    assert box.label is Label.YELLOW_II
    assert box.transport_index == Decimal("0.4")
    assert box.dose_count == 2


def test_a_quiet_package_takes_the_white_label() -> None:
    assert a_shipment(surface_mrem=Decimal("0.2"), metre_mrem=Decimal(0)).label is Label.WHITE_I


def test_a_package_over_the_surface_limit_cannot_be_built() -> None:
    with pytest.raises(ValidationError, match="over the surface limit"):
        a_shipment(surface_mrem=Decimal(400))


def test_an_empty_box_is_not_a_shipment() -> None:
    with pytest.raises(ValidationError, match="empty box"):
        a_shipment(dose_ids=())


def test_a_dose_cannot_be_packed_twice_in_the_same_box() -> None:
    with pytest.raises(ValidationError, match="packed twice"):
        a_shipment(dose_ids=("DS-250408-14", "DS-250408-14"))


def test_the_ids_have_to_be_the_right_kinds() -> None:
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_shipment(dose_ids=("B-250408-01",))
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_shipment(customer_id="AU-0004")


def test_a_shipment_is_signed_and_has_something_in_it() -> None:
    with pytest.raises(ValidationError, match="signed by"):
        a_shipment(packed_by=" ")
    with pytest.raises(ValidationError, match="no activity in it"):
        a_shipment(activity=Activity.zero())


def test_the_a2_fraction_is_small_for_a_morning_of_scans() -> None:
    assert a_shipment().a2_fraction < Decimal("0.01")


def test_a_delivery_puts_a_signature_on_the_box() -> None:
    box = a_shipment()
    assert not box.is_delivered
    signed = box.delivered(at("2025-04-08 09:05"), "J. Fennimore")
    assert signed.is_delivered
    assert signed.received_by == "J. Fennimore"


def test_a_box_cannot_be_delivered_twice_or_unsigned() -> None:
    signed = a_shipment().delivered(at("2025-04-08 09:05"), "J. Fennimore")
    with pytest.raises(ValidationError, match="already been delivered"):
        signed.delivered(at("2025-04-08 10:00"), "Someone Else")
    with pytest.raises(ValidationError, match="signed for"):
        a_shipment().delivered(at("2025-04-08 09:05"), "  ")


def test_a_box_cannot_be_delivered_before_it_was_packed() -> None:
    with pytest.raises(ValidationError, match="delivered before it was packed"):
        a_shipment(delivered_at=at("2025-04-08 07:00"), received_by="J. Fennimore")


def test_the_box_knows_what_is_in_it() -> None:
    assert a_shipment().holds("DS-250408-14")
    assert not a_shipment().holds("DS-250408-99")


def test_the_manifest_line_reads_the_way_the_driver_needs_it() -> None:
    assert a_shipment().manifest_line() == (
        "SH-250408-03 CU-0001 Yellow-II TI 0.4 2 doses 48.0 mCi Tc-99m"
    )
