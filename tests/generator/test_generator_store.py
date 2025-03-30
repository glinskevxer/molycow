import datetime as dt

import pytest
from tests.conftest import at

from molycow.errors import ConflictError, NotFoundError
from molycow.model.generator import Elution, Generator
from molycow.store import Book
from molycow.store.generators import ElutionRepository, GeneratorRepository
from molycow.units import Activity, Volume


def a_generator(generator_id: str = "GEN-0027", **changed: object) -> Generator:
    fields: dict[str, object] = {
        "id": generator_id,
        "serial": f"M99-{generator_id[-4:]}",
        "maker": "Corren Isotopes",
        "calibrated_at": at("2025-04-05 12:00"),
        "calibrated_activity": Activity.of(2, "Ci"),
        "received_on": dt.date(2025, 4, 5),
        "expires_on": dt.date(2025, 4, 19),
    }
    fields.update(changed)
    return Generator(**fields)  # type: ignore[arg-type]


def an_elution(elution_id: str = "EL-250408-01", **changed: object) -> Elution:
    fields: dict[str, object] = {
        "id": elution_id,
        "generator_id": "GEN-0027",
        "drawn_at": at("2025-04-08 06:30"),
        "volume": Volume.of(10),
        "activity": Activity.of(940, "mCi"),
        "expected": Activity.of(1000, "mCi"),
    }
    fields.update(changed)
    return Elution(**fields)  # type: ignore[arg-type]


def test_a_generator_goes_in_and_comes_back_the_same(book: Book) -> None:
    repo = GeneratorRepository(book)
    repo.add(a_generator())
    assert repo.get("GEN-0027") == a_generator()


def test_the_makers_serial_is_unique(book: Book) -> None:
    repo = GeneratorRepository(book)
    repo.add(a_generator())
    with pytest.raises(ConflictError):
        repo.add(a_generator("GEN-0028", serial="M99-0027"))


def test_a_generator_that_is_not_there(book: Book) -> None:
    repo = GeneratorRepository(book)
    assert repo.find("GEN-0404") is None
    with pytest.raises(NotFoundError, match="no such generator"):
        repo.get("GEN-0404")


def test_the_columns_that_may_be_milked_today_are_oldest_first(book: Book) -> None:
    repo = GeneratorRepository(book)
    repo.add(a_generator())
    repo.add(
        a_generator(
            "GEN-0028",
            received_on=dt.date(2025, 3, 29),
            expires_on=dt.date(2025, 4, 12),
        )
    )
    repo.add(
        a_generator(
            "GEN-0026",
            received_on=dt.date(2025, 3, 15),
            expires_on=dt.date(2025, 3, 29),
        )
    )
    ready = repo.in_date_on(dt.date(2025, 4, 8))
    assert [one.id for one in ready] == ["GEN-0028", "GEN-0027"]


def test_retiring_a_column_takes_it_off_the_bench(book: Book) -> None:
    repo = GeneratorRepository(book)
    repo.add(a_generator())
    retired = repo.retire("GEN-0027", dt.date(2025, 4, 10))
    assert retired.retired_on == dt.date(2025, 4, 10)
    assert repo.in_date_on(dt.date(2025, 4, 11)) == []
    assert repo.get("GEN-0027").retired_on == dt.date(2025, 4, 10)


def test_the_next_generator_number_carries_on(book: Book) -> None:
    repo = GeneratorRepository(book)
    assert repo.next_id() == "GEN-0001"
    repo.add(a_generator("GEN-0027"))
    assert repo.next_id() == "GEN-0028"


def test_an_elution_needs_a_generator_that_exists(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        ElutionRepository(book).add(an_elution())


def test_elutions_come_back_in_the_order_they_happened(book: Book) -> None:
    GeneratorRepository(book).add(a_generator())
    repo = ElutionRepository(book)
    repo.add(an_elution("EL-250408-02", drawn_at=at("2025-04-08 13:15")))
    repo.add(an_elution("EL-250408-01"))
    assert [one.id for one in repo.for_generator("GEN-0027")] == [
        "EL-250408-01",
        "EL-250408-02",
    ]
    assert repo.count_for("GEN-0027") == 2


def test_the_last_milking_is_the_one_the_next_expectation_works_from(book: Book) -> None:
    GeneratorRepository(book).add(a_generator())
    repo = ElutionRepository(book)
    assert repo.last_for("GEN-0027") is None
    repo.add(an_elution("EL-250408-01"))
    repo.add(an_elution("EL-250408-02", drawn_at=at("2025-04-08 13:15")))
    last = repo.last_for("GEN-0027")
    assert last is not None
    assert last.id == "EL-250408-02"


def test_an_elution_that_is_not_there(book: Book) -> None:
    repo = ElutionRepository(book)
    assert repo.find("EL-250408-09") is None
    with pytest.raises(NotFoundError, match="no such elution"):
        repo.get("EL-250408-09")


def test_the_days_elutions_are_the_ones_on_the_local_day(book: Book) -> None:
    GeneratorRepository(book).add(a_generator())
    repo = ElutionRepository(book)
    repo.add(an_elution("EL-250407-01", drawn_at=at("2025-04-07 19:30")))
    repo.add(an_elution("EL-250408-01"))
    assert [one.id for one in repo.on_day(dt.date(2025, 4, 8))] == ["EL-250408-01"]
    assert [one.id for one in repo.on_day(dt.date(2025, 4, 7))] == ["EL-250407-01"]


def test_an_elution_survives_the_round_trip_with_its_numbers(book: Book) -> None:
    GeneratorRepository(book).add(a_generator())
    repo = ElutionRepository(book)
    repo.add(an_elution(residual=Activity.of(12, "mCi")))
    back = repo.get("EL-250408-01")
    assert back.activity.format() == "940.000 mCi"
    assert back.residual.format() == "12.000 mCi"
    assert back.volume == Volume.of(10)
    assert back.drawn_at == at("2025-04-08 06:30")
