import datetime as dt

import pytest
from tests.conftest import at

from molycow.errors import ConflictError, NotFoundError
from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
from molycow.model.qc import CheckKind, LinearityPoint, LinearityRun, QcCheck
from molycow.store import Book
from molycow.store.instruments import (
    CheckSourceRepository,
    InstrumentRepository,
    QcRepository,
)
from molycow.units import Activity


def an_instrument(instrument_id: str = "IC-0003", **changed: object) -> Instrument:
    fields: dict[str, object] = {
        "id": instrument_id,
        "kind": InstrumentKind.DOSE_CALIBRATOR,
        "maker": "Vernay",
        "model": "CRC-55tR",
        "serial": f"551-{instrument_id[-4:]}",
        "installed_on": dt.date(2023, 6, 12),
        "calibrated_on": dt.date(2025, 2, 3),
    }
    fields.update(changed)
    return Instrument(**fields)  # type: ignore[arg-type]


def a_source(serial: str = "CS-9912", **changed: object) -> CheckSource:
    fields: dict[str, object] = {
        "serial": serial,
        "symbol": "Cs-137",
        "certified_activity": Activity.of(200, "uci"),
        "certified_on": dt.date(2019, 7, 1),
    }
    fields.update(changed)
    return CheckSource(**fields)  # type: ignore[arg-type]


def a_check(**changed: object) -> QcCheck:
    fields: dict[str, object] = {
        "instrument_id": "IC-0003",
        "kind": CheckKind.CONSTANCY,
        "at": at("2025-04-08 06:15"),
        "source_serial": "CS-9912",
        "expected": Activity.of(163, "uci"),
        "measured": Activity.of(159, "uci"),
        "checked_by": "K. Ruzicka",
    }
    fields.update(changed)
    return QcCheck(**fields)  # type: ignore[arg-type]


def test_an_instrument_goes_in_and_comes_back(book: Book) -> None:
    repo = InstrumentRepository(book)
    repo.add(an_instrument())
    assert repo.get("IC-0003") == an_instrument()
    assert repo.next_id() == "IC-0004"


def test_two_instruments_cannot_share_a_serial(book: Book) -> None:
    repo = InstrumentRepository(book)
    repo.add(an_instrument())
    with pytest.raises(ConflictError):
        repo.add(an_instrument("IC-0004", serial="551-0003"))


def test_instruments_can_be_listed_by_kind_and_by_whether_they_work(book: Book) -> None:
    repo = InstrumentRepository(book)
    repo.add(an_instrument())
    repo.add(an_instrument("IC-0004", kind=InstrumentKind.SURVEY_METER))
    repo.add(an_instrument("IC-0005", calibrated_on=dt.date(2023, 6, 12)))
    calibrators = repo.of_kind(InstrumentKind.DOSE_CALIBRATOR)
    assert [one.id for one in calibrators] == ["IC-0003", "IC-0005"]
    usable = repo.of_kind(InstrumentKind.DOSE_CALIBRATOR, usable_on=dt.date(2025, 4, 8))
    assert [one.id for one in usable] == ["IC-0003"]


def test_recalibrating_moves_the_annual_date(book: Book) -> None:
    repo = InstrumentRepository(book)
    repo.add(an_instrument(calibrated_on=dt.date(2023, 6, 12)))
    fresh = repo.recalibrate("IC-0003", dt.date(2025, 3, 1))
    assert fresh.calibration_due == dt.date(2026, 3, 1)
    assert repo.get("IC-0003").is_usable_on(dt.date(2025, 4, 8))


def test_an_instrument_that_is_not_there(book: Book) -> None:
    repo = InstrumentRepository(book)
    assert repo.find("IC-0404") is None
    with pytest.raises(NotFoundError, match="no such instrument"):
        repo.get("IC-0404")


def test_a_check_source_goes_in_and_comes_back(book: Book) -> None:
    repo = CheckSourceRepository(book)
    repo.add(a_source())
    assert repo.get("CS-9912") == a_source()
    assert [one.serial for one in repo.all()] == ["CS-9912"]


def test_retired_sources_drop_off_the_shelf(book: Book) -> None:
    repo = CheckSourceRepository(book)
    repo.add(a_source())
    repo.add(a_source("CS-2201", symbol="Co-57", retired_on=dt.date(2024, 12, 31)))
    assert [one.serial for one in repo.in_use_on(dt.date(2025, 4, 8))] == ["CS-9912"]


def test_a_source_that_is_not_there(book: Book) -> None:
    repo = CheckSourceRepository(book)
    assert repo.find("CS-0000") is None
    with pytest.raises(NotFoundError, match="no such check source"):
        repo.get("CS-0000")


def test_a_check_needs_an_instrument_and_a_source_that_exist(book: Book) -> None:
    with pytest.raises(Exception, match="not there"):
        QcRepository(book).add(a_check())


def test_checks_come_back_by_instrument_and_by_kind(book: Book) -> None:
    InstrumentRepository(book).add(an_instrument())
    CheckSourceRepository(book).add(a_source())
    repo = QcRepository(book)
    repo.add(a_check())
    repo.add(a_check(kind=CheckKind.ACCURACY, at=at("2025-02-03 09:00")))
    assert len(repo.for_instrument("IC-0003")) == 2
    daily = repo.for_instrument("IC-0003", CheckKind.CONSTANCY)
    assert [one.kind for one in daily] == [CheckKind.CONSTANCY]


def test_the_last_check_of_a_kind_is_the_most_recent(book: Book) -> None:
    InstrumentRepository(book).add(an_instrument())
    CheckSourceRepository(book).add(a_source())
    repo = QcRepository(book)
    repo.add(a_check())
    repo.add(a_check(at=at("2025-04-09 06:20")))
    last = repo.last("IC-0003", CheckKind.CONSTANCY)
    assert last is not None
    assert last.at == at("2025-04-09 06:20")
    assert repo.last("IC-0003", CheckKind.GEOMETRY) is None


def test_the_checks_run_on_one_day(book: Book) -> None:
    InstrumentRepository(book).add(an_instrument())
    CheckSourceRepository(book).add(a_source())
    repo = QcRepository(book)
    repo.add(a_check())
    repo.add(a_check(at=at("2025-04-09 06:20")))
    today = repo.on_day("IC-0003", CheckKind.CONSTANCY, dt.date(2025, 4, 8))
    assert len(today) == 1
    assert repo.on_day("IC-0003", CheckKind.CONSTANCY, dt.date(2025, 4, 10)) == []


def test_a_linearity_run_and_its_readings_go_in_together(book: Book) -> None:
    InstrumentRepository(book).add(an_instrument())
    repo = QcRepository(book)
    run = LinearityRun(
        instrument_id="IC-0003",
        symbol="Tc-99m",
        points=(
            LinearityPoint(at("2025-04-08 07:00"), Activity.of(400, "mci")),
            LinearityPoint(at("2025-04-08 13:00"), Activity.of("200.1", "mci")),
            LinearityPoint(at("2025-04-09 07:00"), Activity.of("25.2", "mci")),
        ),
        checked_by="K. Ruzicka",
    )
    run_id = repo.add_run(run)
    assert repo.get_run(run_id) == run
    assert repo.runs_for("IC-0003") == [run_id]


def test_a_linearity_run_that_is_not_there(book: Book) -> None:
    with pytest.raises(NotFoundError, match="no such linearity run"):
        QcRepository(book).get_run(9)
