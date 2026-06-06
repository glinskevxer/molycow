import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_generator

from molycow.errors import ConflictError, NotFoundError, SafetyError, ValidationError
from molycow.model.receipt import PackageReceipt
from molycow.service.receipt import ReceiptService
from molycow.store import Book
from molycow.store.receipts import ReceiptRepository
from molycow.transport import Label

ARRIVED = at("2025-04-05 07:20")


def a_receipt(**changed: object) -> PackageReceipt:
    fields: dict[str, object] = {
        "reference": "COR-88412",
        "supplier": "Corren Isotopes",
        "received_at": ARRIVED,
        "surface_mrem": Decimal(38),
        "metre_mrem": Decimal("1.4"),
        "wipe_dpm": Decimal(140),
        "received_by": "K. Ruzicka",
    }
    fields.update(changed)
    return PackageReceipt(**fields)  # type: ignore[arg-type]


def test_a_clean_package_carries_its_label_and_index() -> None:
    receipt = a_receipt()
    assert receipt.passes
    assert receipt.label is Label.YELLOW_III
    assert receipt.transport_index == Decimal("1.4")
    assert "clean" in receipt.line()


def test_a_package_over_the_surface_limit_is_not_ours_to_open() -> None:
    hot = a_receipt(surface_mrem=Decimal(260))
    assert not hot.passes
    assert hot.failure() is not None
    assert "surface reading" in hot.line()
    assert hot.label is None


def test_a_package_over_the_index_limit_fails() -> None:
    hot = a_receipt(metre_mrem=Decimal(12))
    assert not hot.index_passes
    assert "transport index" in str(hot.failure())


def test_a_contaminated_package_fails_on_the_wipe() -> None:
    dirty = a_receipt(wipe_dpm=Decimal(4000))
    assert dirty.surface_passes
    assert not dirty.wipe_passes
    assert "wipe 4000 dpm" in str(dirty.failure())


def test_a_receipt_needs_a_reference_a_sender_and_a_signature() -> None:
    with pytest.raises(ValidationError, match="carrier's reference"):
        a_receipt(reference=" ")
    with pytest.raises(ValidationError, match="says who sent it"):
        a_receipt(supplier="")
    with pytest.raises(ValidationError, match="is signed"):
        a_receipt(received_by=" ")
    with pytest.raises(ValidationError, match="cannot be negative"):
        a_receipt(wipe_dpm=Decimal(-1))


def test_a_package_is_booked_in_once(book: Book) -> None:
    service = ReceiptService(book)
    service.receive(
        "COR-88412", "Corren Isotopes", ARRIVED, Decimal(38), Decimal("1.4"), Decimal(140), "K. R"
    )
    with pytest.raises(ConflictError, match="already booked in"):
        service.receive(
            "COR-88412", "Corren Isotopes", ARRIVED, Decimal(38), Decimal("1.4"), Decimal(140), "K"
        )


def test_a_failed_package_stops_anybody_opening_it(book: Book) -> None:
    service = ReceiptService(book)
    service.receive(
        "COR-88412", "Corren Isotopes", ARRIVED, Decimal(260), Decimal("1.4"), Decimal(140), "K. R"
    )
    with pytest.raises(SafetyError, match="must not be opened"):
        service.require_clean("COR-88412")
    assert [one.reference for one in service.failures()] == ["COR-88412"]


def test_a_package_nobody_booked_in(book: Book) -> None:
    service = ReceiptService(book)
    with pytest.raises(NotFoundError, match="no package with that reference"):
        service.require_clean("COR-00000")


def test_a_column_can_be_tied_to_the_package_it_came_in(book: Book) -> None:
    service = ReceiptService(book)
    service.receive(
        "COR-88412", "Corren Isotopes", ARRIVED, Decimal(38), Decimal("1.4"), Decimal(140), "K. R"
    )
    a_generator(book)
    assert service.package_of("GEN-0027") is None
    service.link("GEN-0027", "COR-88412")
    assert service.package_of("GEN-0027") == "COR-88412"


def test_the_days_packages_read_back(book: Book) -> None:
    service = ReceiptService(book)
    service.receive(
        "COR-88412", "Corren Isotopes", ARRIVED, Decimal(38), Decimal("1.4"), Decimal(140), "K. R"
    )
    assert len(service.on_day(dt.date(2025, 4, 5))) == 1
    assert service.on_day(dt.date(2025, 4, 6)) == []
    assert ReceiptRepository(book).get("COR-88412").supplier == "Corren Isotopes"
