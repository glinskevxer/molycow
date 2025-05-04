import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import NotFoundError, RuleError
from molycow.model.generator import Generator
from molycow.model.kit import KitLot
from molycow.service.breakthrough import BreakthroughService
from molycow.service.compound import CompoundService
from molycow.service.elution import ElutionService
from molycow.store import Book
from molycow.store.generators import GeneratorRepository
from molycow.store.kits import BatchRepository, KitLotRepository
from molycow.units import Activity, Volume

DRAWN = at("2025-04-08 06:30")
PREP = at("2025-04-08 07:15")


def a_bench(book: Book, tested: bool = True) -> str:
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
    milking = ElutionService(book).milk("GEN-0027", DRAWN, Volume.of(10), Activity.of(940, "mCi"))
    if tested:
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
    return milking.elution.id


def test_the_volume_falls_out_of_the_concentration_at_prep_time(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    early = service.plan("MDP", elution_id, PREP, Activity.of(300, "mci"))
    late = service.plan("MDP", elution_id, at("2025-04-08 10:15"), Activity.of(300, "mci"))
    assert late.volume > early.volume
    assert early.kit_lot.id == "KL-0114"


def test_compounding_writes_the_batch_with_the_volume_it_took(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    batch = service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")
    assert batch.id == "B-250408-01"
    assert batch.activity.format() == "300.000 mCi"
    assert BatchRepository(book).get(batch.id).volume == batch.volume


def test_what_is_left_in_the_elution_vial_goes_down(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    assert service.remaining_in(elution_id) == Volume.of(10)
    batch = service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")
    assert service.drawn_from(elution_id) == batch.volume
    assert service.remaining_in(elution_id) == Volume.of(10) - batch.volume


def test_a_prep_bigger_than_the_vial_is_refused(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    service.compound("MDP", elution_id, PREP, Activity.of(400, "mci"), "K. Ruzicka")
    with pytest.raises(RuleError, match="not enough left"):
        service.compound(
            "MDP", elution_id, at("2025-04-08 10:15"), Activity.of(400, "mci"), "K. Ruzicka"
        )


def test_a_prep_outside_the_insert_is_refused_before_anything_is_drawn(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    with pytest.raises(Exception, match="outside what the insert allows"):
        service.compound("MDP", elution_id, PREP, Activity.of(50, "mci"), "K. Ruzicka")
    assert service.remaining_in(elution_id) == Volume.of(10)


def test_an_untested_eluate_cannot_be_compounded_from(book: Book) -> None:
    elution_id = a_bench(book, tested=False)
    service = CompoundService(book)
    with pytest.raises(RuleError, match="may not be drawn from"):
        service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")


def test_an_eluate_past_its_shelf_life_cannot_be_compounded_from(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    with pytest.raises(RuleError, match="may not be drawn from"):
        service.compound(
            "MDP", elution_id, at("2025-04-08 19:00"), Activity.of(300, "mci"), "K. Ruzicka"
        )


def test_a_kit_with_no_lot_in_date_stops_the_prep(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    with pytest.raises(NotFoundError, match="no kit of that sort"):
        service.compound("MAA", elution_id, PREP, Activity.of(100, "mci"), "K. Ruzicka")


def test_a_batch_is_held_until_it_has_a_purity_reading(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    batch = service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")
    assert service.ready(at("2025-04-08 08:00")) == []
    held = service.held(at("2025-04-08 08:00"))
    assert [(one.id, why) for one, why in held] == [(batch.id, "no purity reading yet")]


def test_a_tested_batch_is_ready_and_the_strongest_comes_first(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    first = service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")
    second = service.compound(
        "MDP", elution_id, at("2025-04-08 07:30"), Activity.of(300, "mci"), "K. Ruzicka"
    )
    batches = BatchRepository(book)
    batches.record_purity(first.id, Decimal("96.2"))
    batches.record_purity(second.id, Decimal("97.1"))
    moment = at("2025-04-08 08:00")
    ready = service.ready(moment)
    assert {one.id for one in ready} == {first.id, second.id}
    strengths = [one.concentration_at(moment).uci_per_ml for one in ready]
    assert strengths == sorted(strengths, reverse=True)
    assert service.held(moment) == []


def test_a_batch_that_failed_purity_stays_held(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    batch = service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")
    BatchRepository(book).record_purity(batch.id, Decimal("81.5"))
    held = service.held(at("2025-04-08 08:00"))
    assert held[0][1] == "purity under the floor for this kit"


def test_a_batch_that_has_not_been_made_yet_is_not_held_against_the_bench(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    service.compound("MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka")
    assert service.held(at("2025-04-08 07:00")) == []


def test_an_elution_that_is_not_there(book: Book) -> None:
    service = CompoundService(book)
    with pytest.raises(NotFoundError, match="no such elution"):
        service.remaining_in("EL-250408-09")


def test_a_small_activity_is_still_made_up_to_the_inserts_volume(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    batch = service.compound("MDP", elution_id, PREP, Activity.of(120, "mci"), "K. Ruzicka")
    assert batch.volume == Volume.of(3)
    assert batch.eluate_volume < Volume.of(3)
    assert batch.saline > Volume.zero()


def test_the_bench_can_ask_for_a_bigger_made_volume(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    batch = service.compound(
        "MDP", elution_id, PREP, Activity.of(300, "mci"), "K. Ruzicka", volume=Volume.of(8)
    )
    assert batch.volume == Volume.of(8)
    assert batch.concentration.format() == "37.500 mCi/mL"


def test_a_made_volume_smaller_than_the_eluate_needed_is_refused(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    with pytest.raises(RuleError, match="more eluate than the vial"):
        service.compound(
            "MDP", elution_id, PREP, Activity.of(400, "mci"), "K. Ruzicka", volume=Volume.of(3)
        )


def test_only_the_eluate_that_went_in_comes_off_the_elution_vial(book: Book) -> None:
    elution_id = a_bench(book)
    service = CompoundService(book)
    batch = service.compound("MDP", elution_id, PREP, Activity.of(120, "mci"), "K. Ruzicka")
    assert service.drawn_from(elution_id) == batch.eluate_volume
    assert service.remaining_in(elution_id) > Volume.of(7)
