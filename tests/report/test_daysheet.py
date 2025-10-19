import datetime as dt
from decimal import Decimal

from tests.conftest import at
from tests.support import a_working_day

from molycow.model.survey import Area, DoseRate, Wipe
from molycow.report.daysheet import day_sheet
from molycow.service.dispense import DispenseService
from molycow.service.shipping import ShippingService
from molycow.service.survey import SurveyService
from molycow.store import Book

DAY = dt.date(2025, 4, 8)
DRAW = at("2025-04-08 07:40")


def a_full_day(book: Book) -> str:
    day = a_working_day(book)
    dispensing = DispenseService(book)
    planned = dispensing.plan(day.order_id, day.batch_id, DRAW)
    dose = dispensing.draw(
        day.order_id, day.batch_id, DRAW, planned.needed, "K. Ruzicka", day.calibrator_id
    )
    ShippingService(book).pack(
        "CU-0001", [dose.id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    return dose.id


def test_an_empty_day_says_so_in_every_section(book: Book) -> None:
    sheet = day_sheet(book, DAY)
    assert sheet.title == "hot lab day sheet 2025-04-08"
    assert sheet.section("elutions").rows == ()
    assert sheet.section("elutions").lines()[1] == "  no column was milked"
    assert sheet.row_count == 1


def test_the_sheet_carries_every_stage_of_the_day(book: Book) -> None:
    dose_id = a_full_day(book)
    sheet = day_sheet(book, DAY)
    assert len(sheet.section("elutions").rows) == 1
    assert len(sheet.section("batches").rows) == 1
    assert len(sheet.section("doses").rows) == 1
    assert len(sheet.section("shipments").rows) == 1
    assert dose_id in sheet.section("doses").rows[0]


def test_the_elution_row_carries_the_yield_and_the_breakthrough(book: Book) -> None:
    a_full_day(book)
    row = day_sheet(book, DAY).section("elutions").rows[0]
    assert "EL-250408-01 GEN-0027" in row
    assert "yield" in row
    assert "moly 0.00" in row


def test_an_untested_eluate_says_so_on_the_sheet(book: Book) -> None:
    from tests.support import an_elution

    an_elution(book, tested=False)
    row = day_sheet(book, DAY).section("elutions").rows[0]
    assert row.endswith("untested")


def test_the_batch_row_carries_the_purity(book: Book) -> None:
    a_full_day(book)
    row = day_sheet(book, DAY).section("batches").rows[0]
    assert "rcp 95.9%" in row
    assert "MDP" in row


def test_the_dose_row_carries_the_variance_with_its_sign(book: Book) -> None:
    a_full_day(book)
    row = day_sheet(book, DAY).section("doses").rows[0]
    assert "A-4471902" in row
    assert "%" in row
    assert "+" in row or "-" in row


def test_a_box_on_the_dock_reads_differently_from_a_signed_one(book: Book) -> None:
    dose_id = a_full_day(book)
    assert "on the dock" in day_sheet(book, DAY).section("shipments").rows[0]
    shipping = ShippingService(book)
    box = shipping.outstanding()[0]
    shipping.deliver(box.id, at("2025-04-08 09:05"), "Reception")
    assert dose_id
    assert "signed Reception" in day_sheet(book, DAY).section("shipments").rows[0]


def test_the_survey_section_names_the_areas_nobody_walked(book: Book) -> None:
    a_full_day(book)
    rows = day_sheet(book, DAY).section("survey").rows
    assert rows[0].startswith("areas not surveyed:")


def test_a_walked_building_leaves_the_survey_section_clean(book: Book) -> None:
    a_full_day(book)
    SurveyService(book).walk(
        at("2025-04-08 17:40"),
        "K. Ruzicka",
        [
            (Area.HOT_LAB, DoseRate.of("1.2")),
            (Area.DISPENSING, DoseRate.of("0.8")),
            (Area.PACKAGING, DoseRate.of("0.3")),
            (Area.WASTE, DoseRate.of("2.1")),
        ],
        [Wipe(Area.HOT_LAB, "bench", 300, 120, Decimal("0.35"))],
    )
    section = day_sheet(book, DAY).section("survey")
    assert section.rows[0].startswith("hottest reading waste store")


def test_the_holdings_section_shows_the_share_of_the_licence(book: Book) -> None:
    a_full_day(book)
    rows = day_sheet(book, DAY).section("on the premises at midnight").rows
    assert any("Mo-99" in row and "% of limit" in row for row in rows)


def test_the_sheet_renders_as_text_with_its_underline(book: Book) -> None:
    text = day_sheet(book, DAY).text()
    assert text.splitlines()[1] == "=" * len("hot lab day sheet 2025-04-08")
    assert "elutions" in text
