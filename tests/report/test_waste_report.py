from decimal import Decimal

from tests.conftest import at

from molycow.model.waste import ContainerKind
from molycow.report.waste import waste_sheet
from molycow.service.waste import WasteService
from molycow.store import Book
from molycow.units import Activity

OPENED = at("2025-04-08 06:00")
MIDDAY = at("2025-04-08 12:00")


def a_drum(book: Book, nuclide: str = "Tc-99m") -> str:
    service = WasteService(book)
    drum = service.open_container(ContainerKind.VIALS, OPENED)
    service.discard(drum.id, nuclide, Activity.of(40, "mci"), at("2025-04-08 10:30"), "EL-1")
    return drum.id


def test_an_empty_store_says_so_in_every_section(book: Book) -> None:
    sheet = waste_sheet(book, MIDDAY)
    assert sheet.section("holding").is_empty
    assert sheet.section("ready").is_empty
    assert sheet.section("disposed of").is_empty
    assert "0.00 mCi altogether" in sheet.section("in the store").rows[0]


def test_an_open_drum_is_holding_and_says_why(book: Book) -> None:
    a_drum(book)
    rows = waste_sheet(book, MIDDAY).section("holding").rows
    assert rows[0].startswith("WC-0001")
    assert "still open" in rows[0]
    assert "clears" in rows[0]


def test_a_closed_drum_shows_when_it_clears(book: Book) -> None:
    drum_id = a_drum(book)
    WasteService(book).close(drum_id, at("2025-04-08 17:00"))
    rows = waste_sheet(book, at("2025-04-09 09:00")).section("holding").rows
    assert "not held ten half lives yet" in rows[0]


def test_a_drum_past_its_hold_is_ready(book: Book) -> None:
    drum_id = a_drum(book)
    WasteService(book).close(drum_id, at("2025-04-08 17:00"))
    sheet = waste_sheet(book, at("2025-04-12 09:00"))
    assert sheet.section("holding").is_empty
    assert sheet.section("ready").rows[0].startswith("WC-0001")
    assert "left" in sheet.section("ready").rows[0]


def test_a_disposed_drum_keeps_its_reading_and_its_name(book: Book) -> None:
    drum_id = a_drum(book)
    service = WasteService(book)
    service.close(drum_id, at("2025-04-08 17:00"))
    service.dispose(drum_id, at("2025-04-12 09:00"), "K. Ruzicka", Decimal("0.01"))
    sheet = waste_sheet(book, at("2025-04-12 10:00"))
    row = sheet.section("disposed of").rows[0]
    assert "surveyed 0.01 mrem/h" in row
    assert "by K. Ruzicka" in row
    assert sheet.section("holding").is_empty


def test_the_store_total_falls_through_the_day(book: Book) -> None:
    a_drum(book)
    morning = waste_sheet(book, at("2025-04-08 10:30")).section("in the store").rows[0]
    evening = waste_sheet(book, at("2025-04-08 22:30")).section("in the store").rows[0]
    assert morning != evening


def test_a_long_lived_drum_clears_much_later(book: Book) -> None:
    a_drum(book, "I-131")
    row = waste_sheet(book, MIDDAY).section("holding").rows[0]
    assert "clears 2025-0" in row
    assert "clears 2025-04" not in row
