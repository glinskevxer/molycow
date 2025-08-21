import datetime as dt

import pytest
from tests.conftest import at

from molycow.errors import NotFoundError, RuleError, SafetyError
from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
from molycow.model.qc import CheckKind, LinearityPoint
from molycow.service.qc import QcService
from molycow.store import Book
from molycow.store.instruments import CheckSourceRepository, InstrumentRepository
from molycow.units import Activity

DAY = dt.date(2025, 4, 8)
MORNING = at("2025-04-08 06:15")


def a_lab(book: Book, **changed: object) -> None:
    fields: dict[str, object] = {
        "id": "IC-0003",
        "kind": InstrumentKind.DOSE_CALIBRATOR,
        "maker": "Vernay",
        "model": "CRC-55tR",
        "serial": "551-40922",
        "installed_on": dt.date(2023, 6, 12),
        "calibrated_on": dt.date(2025, 2, 3),
    }
    fields.update(changed)
    InstrumentRepository(book).add(Instrument(**fields))  # type: ignore[arg-type]
    CheckSourceRepository(book).add(
        CheckSource(
            serial="CS-9912",
            symbol="Cs-137",
            certified_activity=Activity.of(200, "uci"),
            certified_on=dt.date(2019, 7, 1),
        )
    )


def expected_today(book: Book) -> Activity:
    return CheckSourceRepository(book).get("CS-9912").activity_on(DAY)


def test_the_expected_reading_comes_off_the_certificate(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    result = service.constancy("IC-0003", "CS-9912", MORNING, expected_today(book), "K. Ruzicka")
    assert result.passes
    assert result.check.expected == expected_today(book)
    assert result.note().startswith("IC-0003 constancy passed")


def test_a_reading_a_long_way_off_fails_the_check(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    low = expected_today(book).scaled("0.8")
    result = service.constancy("IC-0003", "CS-9912", MORNING, low, "K. Ruzicka")
    assert not result.passes
    assert [one.kind for one in service.failures()] == [CheckKind.CONSTANCY]


def test_a_calibrator_out_of_annual_calibration_cannot_be_checked(book: Book) -> None:
    a_lab(book, calibrated_on=dt.date(2023, 6, 12))
    service = QcService(book)
    with pytest.raises(RuleError, match="annual calibration has run out"):
        service.constancy("IC-0003", "CS-9912", MORNING, Activity.of(160, "uci"), "K. R")


def test_a_retired_source_cannot_be_used(book: Book) -> None:
    a_lab(book)
    CheckSourceRepository(book).add(
        CheckSource(
            serial="CS-2201",
            symbol="Co-57",
            certified_activity=Activity.of(180, "uci"),
            certified_on=dt.date(2019, 7, 1),
            retired_on=dt.date(2024, 12, 31),
        )
    )
    service = QcService(book)
    with pytest.raises(RuleError, match="not in use that day"):
        service.constancy("IC-0003", "CS-2201", MORNING, Activity.of(90, "uci"), "K. R")


def test_the_bench_is_stopped_until_the_morning_check_passes(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    with pytest.raises(SafetyError, match="not passed its constancy check today"):
        service.require_checked("IC-0003", DAY)
    service.constancy("IC-0003", "CS-9912", MORNING, expected_today(book), "K. Ruzicka")
    assert service.require_checked("IC-0003", DAY).id == "IC-0003"


def test_a_failed_morning_check_does_not_open_the_bench(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    service.constancy(
        "IC-0003", "CS-9912", MORNING, expected_today(book).scaled("0.5"), "K. Ruzicka"
    )
    with pytest.raises(SafetyError, match="not passed its constancy check today"):
        service.require_checked("IC-0003", DAY)


def test_yesterdays_check_does_not_count_for_today(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    service.constancy(
        "IC-0003", "CS-9912", at("2025-04-07 06:15"), expected_today(book), "K. Ruzicka"
    )
    assert service.passed_on("IC-0003", CheckKind.CONSTANCY, dt.date(2025, 4, 7))
    with pytest.raises(SafetyError):
        service.require_checked("IC-0003", DAY)


def test_a_well_counter_does_not_need_a_morning_check(book: Book) -> None:
    a_lab(book, id="IC-0007", kind=InstrumentKind.WELL_COUNTER, serial="WC-1")
    service = QcService(book)
    assert service.require_checked("IC-0007", DAY).id == "IC-0007"


def test_an_instrument_out_of_service_cannot_be_used_at_all(book: Book) -> None:
    a_lab(book, retired_on=dt.date(2025, 3, 31))
    service = QcService(book)
    with pytest.raises(SafetyError, match="not in service that day"):
        service.require_checked("IC-0003", DAY)


def test_every_check_is_overdue_on_an_instrument_that_has_never_been_checked(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    assert service.overdue("IC-0003", DAY) == [
        CheckKind.CONSTANCY,
        CheckKind.LINEARITY,
        CheckKind.ACCURACY,
    ]


def test_a_check_that_has_been_run_drops_off_the_overdue_list(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    service.constancy("IC-0003", "CS-9912", MORNING, expected_today(book), "K. Ruzicka")
    assert CheckKind.CONSTANCY not in service.overdue("IC-0003", DAY)
    assert CheckKind.CONSTANCY in service.overdue("IC-0003", dt.date(2025, 4, 9))


def test_a_linearity_run_is_written_down_with_its_readings(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    run = service.linearity(
        "IC-0003",
        "Tc-99m",
        [
            LinearityPoint(at("2025-04-08 07:00"), Activity.of(400, "mci")),
            LinearityPoint(at("2025-04-08 13:00"), Activity.of("200.1", "mci")),
            LinearityPoint(at("2025-04-09 07:00"), Activity.of("25.2", "mci")),
        ],
        "K. Ruzicka",
    )
    assert run.passes()
    assert len(service.history("IC-0003")) == 0


def test_a_check_against_an_instrument_that_is_not_there(book: Book) -> None:
    service = QcService(book)
    with pytest.raises(NotFoundError, match="no such instrument"):
        service.constancy("IC-0404", "CS-9912", MORNING, Activity.of(1, "uci"), "K. R")


def test_the_history_of_one_instrument_comes_back_in_order(book: Book) -> None:
    a_lab(book)
    service = QcService(book)
    service.constancy("IC-0003", "CS-9912", at("2025-04-07 06:15"), Activity.of(160, "uci"), "KR")
    service.constancy("IC-0003", "CS-9912", MORNING, Activity.of(161, "uci"), "KR")
    history = service.history("IC-0003", CheckKind.CONSTANCY)
    assert [one.at for one in history] == [at("2025-04-07 06:15"), MORNING]
