import csv
import datetime as dt
from decimal import Decimal
from pathlib import Path

from tests.conftest import at
from tests.support import a_working_day

from molycow.report.export import export_day
from molycow.service.dispense import DispenseService
from molycow.service.shipping import ShippingService
from molycow.store import Book

DAY = dt.date(2025, 4, 8)


def a_day_of_work(book: Book) -> str:
    day = a_working_day(book)
    dispensing = DispenseService(book)
    planned = dispensing.plan(day.order_id, day.batch_id, at("2025-04-08 07:40"))
    dose = dispensing.draw(
        day.order_id,
        day.batch_id,
        at("2025-04-08 07:40"),
        planned.needed,
        "K. Ruzicka",
        day.calibrator_id,
    )
    ShippingService(book).pack(
        "CU-0001", [dose.id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    return dose.id


def rows_of(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_an_empty_day_writes_headers_and_nothing_else(book: Book, tmp_path: Path) -> None:
    written = export_day(book, DAY, tmp_path)
    assert [one.rows for one in written] == [0, 0, 0, 0]
    for one in written:
        assert one.path.exists()
        assert rows_of(one.path) == []


def test_a_days_work_lands_in_four_files(book: Book, tmp_path: Path) -> None:
    a_day_of_work(book)
    written = export_day(book, DAY, tmp_path)
    names = [one.path.name for one in written]
    assert names == ["elutions.csv", "batches.csv", "doses.csv", "shipments.csv"]
    assert [one.rows for one in written] == [1, 1, 1, 1]


def test_the_dose_row_carries_the_identifiers_to_join_on(book: Book, tmp_path: Path) -> None:
    dose_id = a_day_of_work(book)
    export_day(book, DAY, tmp_path)
    row = rows_of(tmp_path / "doses.csv")[0]
    assert row["id"] == dose_id
    assert row["customer"] == "CU-0001"
    assert row["patient_ref"] == "A-4471902"
    assert row["batch"] == "B-250408-01"


def test_the_numbers_go_out_as_they_are_stored(book: Book, tmp_path: Path) -> None:
    a_day_of_work(book)
    export_day(book, DAY, tmp_path)
    row = rows_of(tmp_path / "elutions.csv")[0]
    assert row["activity_uci"] == "940000.000"
    assert row["volume_ml"] == "10.000"


def test_a_batch_with_no_purity_leaves_the_column_empty(book: Book, tmp_path: Path) -> None:
    from tests.support import a_batch

    a_batch(book)
    export_day(book, DAY, tmp_path)
    assert rows_of(tmp_path / "batches.csv")[0]["rcp"] == ""


def test_an_undelivered_box_leaves_the_delivery_column_empty(book: Book, tmp_path: Path) -> None:
    a_day_of_work(book)
    export_day(book, DAY, tmp_path)
    assert rows_of(tmp_path / "shipments.csv")[0]["delivered_at"] == ""


def test_the_folder_is_made_if_it_is_not_there(book: Book, tmp_path: Path) -> None:
    target = tmp_path / "not" / "there"
    export_day(book, DAY, target)
    assert target.is_dir()


def test_a_written_file_prints_its_row_count(book: Book, tmp_path: Path) -> None:
    a_day_of_work(book)
    written = export_day(book, DAY, tmp_path)
    assert written[0].line().strip().startswith("1  elutions.csv")
