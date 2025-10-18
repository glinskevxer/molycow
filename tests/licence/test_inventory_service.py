from decimal import Decimal

import pytest
from tests.conftest import at
from tests.support import a_generator, a_working_day, an_elution

from molycow.errors import RuleError
from molycow.model.waste import ContainerKind
from molycow.service.dispense import DispenseService
from molycow.service.inventory import InventoryService
from molycow.service.shipping import ShippingService
from molycow.service.waste import WasteService
from molycow.store import Book
from molycow.store.licence import LicenceRepository
from molycow.units import Activity

MORNING = at("2025-04-08 08:00")


def test_a_generator_on_the_bench_is_molybdenum_in_the_building(book: Book) -> None:
    a_generator(book)
    service = InventoryService(book)
    holdings = service.holdings(MORNING)
    assert holdings["Mo-99"].place("generators").format("ci", 2) == "0.98 Ci"


def test_a_retired_generator_has_gone_back(book: Book) -> None:
    import datetime as dt

    from molycow.store.generators import GeneratorRepository

    a_generator(book)
    GeneratorRepository(book).retire("GEN-0027", dt.date(2025, 4, 7))
    assert InventoryService(book).holding_of("Mo-99", MORNING).is_zero()


def test_an_eluate_shows_as_technetium_until_it_is_drawn_down(book: Book) -> None:
    an_elution(book)
    service = InventoryService(book)
    holdings = service.holdings(MORNING)
    assert holdings["Tc-99m"].place("eluate") > Activity.of(500, "mci")


def test_a_batch_takes_its_share_out_of_the_eluate(book: Book) -> None:
    day = a_working_day(book)
    service = InventoryService(book)
    holdings = service.holdings(MORNING)
    assert holdings["Tc-99m"].place("batches") > Activity.zero()
    assert holdings["Tc-99m"].place("eluate") > Activity.zero()
    assert day.batch_id


def test_a_dose_is_here_until_the_box_is_signed_for(book: Book) -> None:
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
    service = InventoryService(book)
    assert service.holdings(MORNING)["Tc-99m"].place("doses") > Activity.zero()
    shipping = ShippingService(book)
    box = shipping.pack(
        "CU-0001", [dose.id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    assert service.holdings(at("2025-04-08 08:30"))["Tc-99m"].place("doses") > Activity.zero()
    shipping.deliver(box.id, at("2025-04-08 09:05"), "Reception")
    assert service.holdings(at("2025-04-08 09:30"))["Tc-99m"].place("doses").is_zero()


def test_waste_still_counts_until_the_drum_goes(book: Book) -> None:
    waste = WasteService(book)
    drum = waste.open_container(ContainerKind.VIALS, at("2025-04-08 06:00"))
    waste.discard(drum.id, "Tc-99m", Activity.of(40, "mci"), at("2025-04-08 07:00"), "EL-1")
    service = InventoryService(book)
    assert service.holdings(MORNING)["Tc-99m"].place("waste") > Activity.zero()
    waste.close(drum.id, at("2025-04-08 17:00"))
    waste.dispose(drum.id, at("2025-04-12 09:00"), "K. Ruzicka", Decimal("0.01"))
    assert service.holding_of("Tc-99m", at("2025-04-12 10:00")).is_zero()


def test_the_holding_falls_through_the_day_on_its_own(book: Book) -> None:
    an_elution(book)
    service = InventoryService(book)
    morning = service.holding_of("Tc-99m", MORNING)
    afternoon = service.holding_of("Tc-99m", at("2025-04-08 14:00"))
    assert afternoon < morning


def test_every_holding_is_checked_against_the_licence(book: Book) -> None:
    a_generator(book)
    checks = InventoryService(book).check(MORNING)
    assert checks[0].holding.symbol == "Mo-99"
    assert checks[0].limit is not None
    assert not checks[0].over
    assert InventoryService(book).over_limit(MORNING) == []


def test_a_nuclide_the_licence_does_not_name_has_no_share(book: Book) -> None:
    waste = WasteService(book)
    drum = waste.open_container(ContainerKind.VIALS, at("2025-04-08 06:00"))
    waste.discard(drum.id, "Y-90", Activity.of(10, "mci"), at("2025-04-08 07:00"), "DS-1")
    checks = InventoryService(book).check(MORNING)
    yttrium = next(one for one in checks if one.holding.symbol == "Y-90")
    assert yttrium.limit is None
    assert yttrium.share is None
    assert not yttrium.over


def test_a_delivery_that_would_break_the_limit_is_refused(book: Book) -> None:
    a_generator(book)
    service = InventoryService(book)
    with pytest.raises(RuleError, match="over its possession limit"):
        service.require_room_for("Mo-99", Activity.of("19.5", "ci"), MORNING)
    assert service.require_room_for("Mo-99", Activity.of(2, "ci"), MORNING) > Activity.zero()


def test_a_delivery_of_something_the_licence_does_not_name_is_refused(book: Book) -> None:
    service = InventoryService(book)
    with pytest.raises(RuleError, match="does not name that nuclide"):
        service.require_room_for("Y-90", Activity.of(1, "mci"), MORNING)


def test_a_lowered_limit_can_put_the_building_over(book: Book) -> None:
    a_generator(book)
    LicenceRepository(book).set_limit("Mo-99", "0.5", "licence amended down")
    over = InventoryService(book).over_limit(MORNING)
    assert [one.holding.symbol for one in over] == ["Mo-99"]
