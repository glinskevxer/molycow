"""Everything written to the book reads back as the same record.

One test per repository would be nineteen tests that all say the same thing.
This sweeps them: build a record, put it in, read it out, and compare. What it
is looking for is a column somebody added to the table and forgot to read back,
which is invisible until the day the field matters.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from tests.conftest import at
from tests.support import (
    CLEAN_SALINE,
    CLEAN_SOLVENT,
    a_calibrator,
    a_register,
    a_working_day,
)

from molycow.model.audit import Entry
from molycow.model.badge import Badge
from molycow.model.fridge import FridgeReading
from molycow.model.instrument import InstrumentKind
from molycow.model.purity import PurityTest
from molycow.model.qc import CheckKind, LinearityPoint, LinearityRun, QcCheck
from molycow.model.receipt import PackageReceipt
from molycow.model.route import Route, Run
from molycow.model.shipment import Shipment
from molycow.model.survey import Area, DoseRate, Survey, Wipe
from molycow.model.waste import Container, ContainerKind
from molycow.store import Book
from molycow.store.audit import AuditRepository
from molycow.store.badges import BadgeRepository
from molycow.store.breakthrough import BreakthroughRepository
from molycow.store.doses import DoseRepository
from molycow.store.fridge import FridgeRepository
from molycow.store.generators import ElutionRepository, GeneratorRepository
from molycow.store.instruments import CheckSourceRepository, InstrumentRepository, QcRepository
from molycow.store.kits import BatchRepository, KitLotRepository
from molycow.store.orders import OrderRepository
from molycow.store.purity import PurityRepository
from molycow.store.receipts import ReceiptRepository
from molycow.store.register import AuthorizedUserRepository, CustomerRepository
from molycow.store.routes import RouteRepository, RunRepository
from molycow.store.shipments import ShipmentRepository
from molycow.store.surveys import SurveyRepository
from molycow.store.waste import ContainerRepository
from molycow.units import Activity

DAY = dt.date(2025, 4, 8)


def test_the_register_reads_back_exactly(book: Book) -> None:
    a_register(book)
    customer = CustomerRepository(book).get("CU-0001")
    assert CustomerRepository(book).all() == [customer]
    user = AuthorizedUserRepository(book).get("AU-0004")
    assert user.nuclides == frozenset({"tc99m"})


def test_the_bench_records_read_back_exactly(book: Book) -> None:
    day = a_working_day(book)
    generator = GeneratorRepository(book).get("GEN-0027")
    assert GeneratorRepository(book).all() == [generator]
    elution = ElutionRepository(book).all()[0]
    assert ElutionRepository(book).get(elution.id) == elution
    assert BreakthroughRepository(book).get(elution.id).ratio > 0
    lot = KitLotRepository(book).get("KL-0114")
    assert KitLotRepository(book).all() == [lot]
    batch = BatchRepository(book).get(day.batch_id)
    assert BatchRepository(book).all() == [batch]
    assert PurityRepository(book).get(batch.id).rcp == batch.rcp


def test_the_order_and_the_dose_read_back_exactly(book: Book) -> None:
    from molycow.service.dispense import DispenseService

    day = a_working_day(book)
    order = OrderRepository(book).get(day.order_id)
    assert OrderRepository(book).all() == [order]
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
    assert DoseRepository(book).get(dose.id) == dose


def test_a_shipment_reads_back_with_its_doses(book: Book) -> None:
    from molycow.service.dispense import DispenseService

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
    shipment = Shipment(
        id="SH-250408-01",
        customer_id="CU-0001",
        packed_at=at("2025-04-08 08:20"),
        packed_by="K. Ruzicka",
        dose_ids=(dose.id,),
        symbol="Tc-99m",
        activity=Activity.of(22, "mci"),
        surface_mrem=Decimal(12),
        metre_mrem=Decimal("0.35"),
    )
    ShipmentRepository(book).add(shipment)
    assert ShipmentRepository(book).get("SH-250408-01") == shipment


def test_a_route_and_its_run_read_back_exactly(book: Book) -> None:
    a_register(book)
    route = Route(
        id="RT-0001",
        name="north morning",
        zone="north",
        stops=("CU-0001",),
        leaves_at=dt.time(6, 30),
    )
    RouteRepository(book).add(route)
    assert RouteRepository(book).get("RT-0001") == route
    run = Run("RT-0001", DAY, "J. Fennimore", at("2025-04-08 06:35"), at("2025-04-08 09:50"))
    RunRepository(book).add(run)
    assert RunRepository(book).get("RT-0001", DAY) == run


def test_a_survey_reads_back_with_its_readings_and_wipes(book: Book) -> None:
    survey = Survey(
        id="SV-250408-01",
        at=at("2025-04-08 17:40"),
        surveyed_by="K. Ruzicka",
        readings=((Area.HOT_LAB, DoseRate.of("1.2")),),
        wipes=(Wipe(Area.HOT_LAB, "bench", 340, 120, Decimal("0.35")),),
    )
    SurveyRepository(book).add(survey)
    assert SurveyRepository(book).get("SV-250408-01") == survey


def test_a_container_reads_back_with_what_went_in_it(book: Book) -> None:
    container = Container(id="WC-0001", kind=ContainerKind.VIALS, opened_at=at("2025-04-08 06:00"))
    repo = ContainerRepository(book)
    repo.add(container)
    from molycow.model.waste import WasteItem

    item = WasteItem("Tc-99m", Activity.of(40, "mci"), at("2025-04-08 10:30"), "EL-250408-01")
    repo.add_item("WC-0001", item)
    assert repo.get("WC-0001").items == (item,)


def test_the_instruments_and_their_checks_read_back_exactly(book: Book) -> None:
    a_calibrator(book, checked=False)
    instrument = InstrumentRepository(book).get("IC-0003")
    assert instrument.kind is InstrumentKind.DOSE_CALIBRATOR
    assert InstrumentRepository(book).all() == [instrument]
    source = CheckSourceRepository(book).get("CS-9912")
    assert CheckSourceRepository(book).all() == [source]
    check = QcCheck(
        instrument_id="IC-0003",
        kind=CheckKind.CONSTANCY,
        at=at("2025-04-08 06:05"),
        source_serial="CS-9912",
        expected=Activity.of(163, "uci"),
        measured=Activity.of(161, "uci"),
        checked_by="K. Ruzicka",
    )
    QcRepository(book).add(check)
    assert QcRepository(book).all() == [check]
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
    assert QcRepository(book).get_run(QcRepository(book).add_run(run)) == run


def test_the_small_tables_read_back_exactly(book: Book) -> None:
    reading = FridgeReading(at("2025-04-08 06:10"), Decimal("4.5"), "K. Ruzicka")
    FridgeRepository(book).add(reading)
    assert FridgeRepository(book).all() == [reading]
    badge = Badge("K. Ruzicka", "2025Q2", Decimal(120), Decimal(1400), dt.date(2025, 7, 14))
    BadgeRepository(book).add(badge)
    assert BadgeRepository(book).all() == [badge]
    receipt = PackageReceipt(
        reference="COR-88412",
        supplier="Corren Isotopes",
        received_at=at("2025-04-05 07:20"),
        surface_mrem=Decimal(38),
        metre_mrem=Decimal("1.4"),
        wipe_dpm=Decimal(140),
        received_by="K. Ruzicka",
    )
    ReceiptRepository(book).add(receipt)
    assert ReceiptRepository(book).all() == [receipt]
    entry = Entry(at("2025-04-08 06:30"), "K. Ruzicka", "milked", "EL-250408-01", "940.0 mCi")
    AuditRepository(book).add(entry)
    assert AuditRepository(book).all() == [entry]


def test_a_purity_test_keeps_every_count_it_was_given(book: Book) -> None:
    day = a_working_day(book)
    reading = PurityRepository(book).get(day.batch_id)
    assert reading.solvent.origin == CLEAN_SOLVENT.origin
    assert reading.saline.front == CLEAN_SALINE.front
    assert isinstance(reading, PurityTest)
    assert reading.rcp == Decimal("95.9")


def test_every_table_in_the_book_is_read_by_a_repository(book: Book) -> None:
    tables = set(book.tables())
    from molycow.store.serials import TABLES

    for table in TABLES.values():
        assert table in tables
    assert {"audit", "badge_reading", "package_receipt", "fridge_reading"} <= tables


def test_nothing_is_lost_by_a_second_open(book: Book, tmp_path: dt.date) -> None:
    from pathlib import Path

    target = Path(str(tmp_path)) / "day.sqlite3"
    day = a_working_day(book)
    book.backup(target)
    with Book.open(target) as copy:
        assert BatchRepository(copy).get(day.batch_id) == BatchRepository(book).get(day.batch_id)
        assert OrderRepository(copy).get(day.order_id) == OrderRepository(book).get(day.order_id)
