import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ConflictError, NotFoundError
from molycow.model import AuthorizedUser, Customer, CustomerKind
from molycow.model.dose import Dose
from molycow.model.generator import Generator
from molycow.model.kit import KitLot
from molycow.model.order import Order
from molycow.service.breakthrough import BreakthroughService
from molycow.service.compound import CompoundService
from molycow.service.elution import ElutionService
from molycow.store import Book
from molycow.store.doses import DoseRepository
from molycow.store.generators import GeneratorRepository
from molycow.store.kits import KitLotRepository
from molycow.store.orders import OrderRepository
from molycow.store.register import AuthorizedUserRepository, CustomerRepository
from molycow.units import Activity, Volume

DRAWN = at("2025-04-08 07:40")
CALIBRATION = at("2025-04-08 09:00")


def a_day(book: Book) -> str:
    CustomerRepository(book).add(
        Customer(
            id="CU-0001",
            name="Saint Brannon Medical Centre",
            kind=CustomerKind.HOSPITAL,
            licence="42-28931-01",
            street="1400 Weir Street",
            town="Ardmore",
            zone="north",
            opened_on=dt.date(2025, 1, 6),
        )
    )
    AuthorizedUserRepository(book).add(
        AuthorizedUser(
            id="AU-0004",
            customer_id="CU-0001",
            name="R. Okonkwo",
            licence="42-28931-01",
            added_on=dt.date(2025, 1, 6),
            nuclides=frozenset({"Tc-99m"}),
        )
    )
    OrderRepository(book).add(
        Order(
            id="ORD-250407-11",
            customer_id="CU-0001",
            user_id="AU-0004",
            code="MDP",
            procedure="whole body bone",
            patient_ref="A-4471902",
            activity=Activity.of(22, "mci"),
            calibration_at=CALIBRATION,
            ordered_at=at("2025-04-07 16:10"),
        )
    )
    GeneratorRepository(book).add(
        Generator(
            id="GEN-0027",
            serial="M99-44182",
            maker="Corren Isotopes",
            calibrated_at=at("2025-04-05 12:00"),
            calibrated_activity=Activity.of(2, "Ci"),
            received_on=dt.date(2025, 4, 5),
            expires_on=dt.date(2025, 4, 19),
        )
    )
    milking = ElutionService(book).milk(
        "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(940, "mCi")
    )
    BreakthroughService(book).test(
        milking.elution.id, at("2025-04-08 06:45"), Activity.of("0.9", "uci"), Decimal(4), "KR"
    )
    KitLotRepository(book).add(
        KitLot(
            id="KL-0114",
            code="MDP",
            maker="Sedgwick Radiochem",
            lot="9F4471",
            received_on=dt.date(2025, 3, 20),
            expires_on=dt.date(2026, 3, 31),
            vials=30,
        )
    )
    batch = CompoundService(book).compound(
        "MDP", milking.elution.id, at("2025-04-08 07:15"), Activity.of(300, "mci"), "K. Ruzicka"
    )
    return batch.id


def a_dose(dose_id: str = "DS-250408-14", **changed: object) -> Dose:
    fields: dict[str, object] = {
        "id": dose_id,
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


def test_a_dose_goes_in_and_comes_back_the_same(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    assert repo.get("DS-250408-14") == a_dose()


def test_a_dose_needs_an_order_and_a_batch_that_exist(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        DoseRepository(book).add(a_dose())


def test_an_order_is_only_filled_once(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    with pytest.raises(ConflictError):
        repo.add(a_dose("DS-250408-15"))


def test_a_dose_is_found_by_its_order_and_its_batch(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    found = repo.for_order("ORD-250407-11")
    assert found is not None
    assert found.id == "DS-250408-14"
    assert [one.id for one in repo.for_batch("B-250408-01")] == ["DS-250408-14"]
    assert repo.for_order("ORD-250407-12") is None


def test_the_days_doses_are_the_ones_drawn_that_day(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    repo.add(a_dose())
    assert repo.count_on(dt.date(2025, 4, 8)) == 1
    assert repo.on_day(dt.date(2025, 4, 9)) == []


def test_the_next_dose_number_restarts_each_morning(book: Book) -> None:
    a_day(book)
    repo = DoseRepository(book)
    assert repo.next_id(dt.date(2025, 4, 8)) == "DS-250408-01"
    repo.add(a_dose())
    assert repo.next_id(dt.date(2025, 4, 8)) == "DS-250408-15"
    assert repo.next_id(dt.date(2025, 4, 9)) == "DS-250409-01"


def test_a_dose_that_is_not_there(book: Book) -> None:
    repo = DoseRepository(book)
    assert repo.find("DS-250408-99") is None
    with pytest.raises(NotFoundError, match="no such dose"):
        repo.get("DS-250408-99")
