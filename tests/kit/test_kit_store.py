import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ConflictError, NotFoundError
from molycow.model.generator import Generator
from molycow.model.kit import Batch, KitLot
from molycow.service.elution import ElutionService
from molycow.store import Book
from molycow.store.generators import GeneratorRepository
from molycow.store.kits import BatchRepository, KitLotRepository
from molycow.units import Activity, Volume


def a_lot(lot_id: str = "KL-0114", **changed: object) -> KitLot:
    fields: dict[str, object] = {
        "id": lot_id,
        "code": "MDP",
        "maker": "Sedgwick Radiochem",
        "lot": f"9F{lot_id[-4:]}",
        "received_on": dt.date(2025, 3, 20),
        "expires_on": dt.date(2026, 3, 31),
        "vials": 30,
    }
    fields.update(changed)
    return KitLot(**fields)  # type: ignore[arg-type]


def an_elution(book: Book) -> str:
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
    return milking.elution.id


def a_batch(batch_id: str = "B-250408-01", **changed: object) -> Batch:
    fields: dict[str, object] = {
        "id": batch_id,
        "kit_lot_id": "KL-0114",
        "elution_id": "EL-250408-01",
        "code": "MDP",
        "made_at": at("2025-04-08 07:15"),
        "activity": Activity.of(300, "mci"),
        "volume": Volume.of(6),
        "eluate_volume": Volume.of("3.5"),
        "made_by": "K. Ruzicka",
    }
    fields.update(changed)
    return Batch(**fields)  # type: ignore[arg-type]


def test_a_kit_lot_goes_in_and_comes_back(book: Book) -> None:
    repo = KitLotRepository(book)
    repo.add(a_lot())
    assert repo.get("KL-0114") == a_lot()
    assert repo.count() == 1


def test_the_same_maker_lot_of_the_same_kit_twice_is_a_conflict(book: Book) -> None:
    repo = KitLotRepository(book)
    repo.add(a_lot())
    with pytest.raises(ConflictError):
        repo.add(a_lot("KL-0115", lot="9F0114"))


def test_a_kit_lot_that_is_not_there(book: Book) -> None:
    repo = KitLotRepository(book)
    assert repo.find("KL-0404") is None
    with pytest.raises(NotFoundError, match="no such kit lot"):
        repo.get("KL-0404")


def test_the_bench_reaches_for_the_lot_nearest_its_expiry(book: Book) -> None:
    repo = KitLotRepository(book)
    repo.add(a_lot())
    repo.add(a_lot("KL-0115", expires_on=dt.date(2025, 9, 30)))
    repo.add(a_lot("KL-0116", expires_on=dt.date(2025, 4, 1)))
    oldest = repo.oldest_in_date("MDP", dt.date(2025, 4, 8))
    assert oldest is not None
    assert oldest.id == "KL-0115"
    assert [one.id for one in repo.for_code("MDP")] == ["KL-0116", "KL-0115", "KL-0114"]


def test_nothing_in_date_leaves_the_bench_with_nothing(book: Book) -> None:
    repo = KitLotRepository(book)
    repo.add(a_lot("KL-0116", expires_on=dt.date(2025, 4, 1)))
    assert repo.oldest_in_date("MDP", dt.date(2025, 4, 8)) is None
    assert repo.oldest_in_date("SESTA", dt.date(2025, 4, 8)) is None


def test_the_next_kit_lot_number_carries_on(book: Book) -> None:
    repo = KitLotRepository(book)
    assert repo.next_id() == "KL-0001"
    repo.add(a_lot())
    assert repo.next_id() == "KL-0115"


def test_a_batch_needs_a_kit_lot_and_an_elution(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        BatchRepository(book).add(a_batch())


def test_a_batch_survives_the_round_trip(book: Book) -> None:
    an_elution(book)
    KitLotRepository(book).add(a_lot())
    repo = BatchRepository(book)
    repo.add(a_batch())
    back = repo.get("B-250408-01")
    assert back.activity.format() == "300.000 mCi"
    assert back.volume == Volume.of(6)
    assert back.rcp is None
    assert repo.untested() == [back]


def test_a_purity_reading_is_written_onto_the_batch(book: Book) -> None:
    an_elution(book)
    KitLotRepository(book).add(a_lot())
    repo = BatchRepository(book)
    repo.add(a_batch())
    tested = repo.record_purity("B-250408-01", Decimal("96.4"))
    assert tested.is_pure_enough
    assert repo.get("B-250408-01").rcp == Decimal("96.4")
    assert repo.untested() == []


def test_batches_are_found_by_elution_and_by_day(book: Book) -> None:
    an_elution(book)
    KitLotRepository(book).add(a_lot())
    repo = BatchRepository(book)
    repo.add(a_batch())
    repo.add(a_batch("B-250408-02", code="MAA", activity=Activity.of(100, "mci")))
    assert len(repo.for_elution("EL-250408-01")) == 2
    assert len(repo.on_day(dt.date(2025, 4, 8))) == 2
    assert repo.on_day(dt.date(2025, 4, 9)) == []


def test_the_batches_still_good_at_a_moment(book: Book) -> None:
    an_elution(book)
    KitLotRepository(book).add(a_lot())
    repo = BatchRepository(book)
    repo.add(a_batch())
    repo.add(a_batch("B-250408-02", code="MAA", activity=Activity.of(100, "mci")))
    at_ten = repo.in_date_at(at("2025-04-08 10:00"))
    assert len(at_ten) == 2
    assert [one.id for one in repo.in_date_at(at("2025-04-08 10:00"), code="MAA")] == [
        "B-250408-02"
    ]
    assert [one.id for one in repo.in_date_at(at("2025-04-08 14:00"))] == ["B-250408-02"]


def test_the_next_batch_number_restarts_each_morning(book: Book) -> None:
    an_elution(book)
    KitLotRepository(book).add(a_lot())
    repo = BatchRepository(book)
    assert repo.next_id(dt.date(2025, 4, 8)) == "B-250408-01"
    repo.add(a_batch())
    assert repo.next_id(dt.date(2025, 4, 8)) == "B-250408-02"
    assert repo.next_id(dt.date(2025, 4, 9)) == "B-250409-01"


def test_a_batch_that_is_not_there(book: Book) -> None:
    repo = BatchRepository(book)
    assert repo.find("B-250408-09") is None
    with pytest.raises(NotFoundError, match="no such batch"):
        repo.get("B-250408-09")
