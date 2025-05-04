import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.kit import Batch, KitLot
from molycow.units import Activity, Volume

MADE = at("2025-04-08 07:15")


def a_lot(**changed: object) -> KitLot:
    fields: dict[str, object] = {
        "id": "KL-0114",
        "code": "MDP",
        "maker": "Sedgwick Radiochem",
        "lot": "9F4471",
        "received_on": dt.date(2025, 3, 20),
        "expires_on": dt.date(2026, 3, 31),
        "vials": 30,
    }
    fields.update(changed)
    return KitLot(**fields)  # type: ignore[arg-type]


def a_batch(**changed: object) -> Batch:
    fields: dict[str, object] = {
        "id": "B-250408-01",
        "kit_lot_id": "KL-0114",
        "elution_id": "EL-250408-01",
        "code": "MDP",
        "made_at": MADE,
        "activity": Activity.of(300, "mci"),
        "volume": Volume.of(6),
        "eluate_volume": Volume.of("3.5"),
        "made_by": "K. Ruzicka",
    }
    fields.update(changed)
    return Batch(**fields)  # type: ignore[arg-type]


def test_a_kit_lot_knows_its_monograph() -> None:
    assert a_lot().formula.name == "medronate"
    assert a_lot(code=" mdp ").code == "MDP"


def test_a_kit_lot_needs_the_makers_lot_number() -> None:
    with pytest.raises(ValidationError, match="maker's lot number"):
        a_lot(lot="  ")


def test_an_empty_kit_lot_is_not_a_lot() -> None:
    with pytest.raises(ValidationError, match="no vials"):
        a_lot(vials=0)


def test_a_kit_lot_cannot_expire_before_it_arrived() -> None:
    with pytest.raises(ValidationError, match="expired before it arrived"):
        a_lot(expires_on=dt.date(2025, 3, 1))


def test_a_kit_lot_is_in_date_between_its_dates() -> None:
    lot = a_lot()
    assert lot.is_in_date(dt.date(2025, 4, 8))
    assert not lot.is_in_date(dt.date(2026, 4, 1))
    assert lot.days_left(dt.date(2026, 3, 1)) == 30


def test_a_batch_takes_its_shelf_life_from_the_monograph() -> None:
    assert a_batch().expires_at == at("2025-04-08 13:15")
    sesta = a_batch(
        code="SESTA",
        activity=Activity.of(140, "mci"),
        volume=Volume.of(2),
        eluate_volume=Volume.of("1.6"),
    )
    assert sesta.expires_at == at("2025-04-08 13:15")
    maa = a_batch(code="MAA", activity=Activity.of(100, "mci"), volume=Volume.of(6))
    assert maa.expires_at == at("2025-04-08 15:15")


def test_a_batch_outside_the_insert_is_refused_when_it_is_made() -> None:
    with pytest.raises(ValidationError, match="outside what the insert allows"):
        a_batch(activity=Activity.of(500, "mci"))
    with pytest.raises(ValidationError, match="outside what the insert allows"):
        a_batch(volume=Volume.of(1), eluate_volume=Volume.of("0.9"))


def test_a_batch_is_signed() -> None:
    with pytest.raises(ValidationError, match="signed by"):
        a_batch(made_by="   ")


def test_a_batch_decays_from_the_moment_it_was_made() -> None:
    batch = a_batch()
    assert batch.concentration.format() == "50.000 mCi/mL"
    assert batch.activity_at(at("2025-04-08 13:15")).format("mci", 0) == "150 mCi"
    assert batch.concentration_at(at("2025-04-08 13:15")).format("mci", 1) == "25.0 mCi/mL"


def test_a_batch_has_no_activity_before_it_was_made() -> None:
    with pytest.raises(ValidationError, match="before it was made"):
        a_batch().activity_at(at("2025-04-08 07:00"))


def test_a_batch_is_in_date_for_its_shelf_life() -> None:
    batch = a_batch()
    assert batch.is_in_date_at(MADE)
    assert batch.is_in_date_at(at("2025-04-08 13:15"))
    assert not batch.is_in_date_at(at("2025-04-08 13:16"))


def test_an_untested_batch_is_held() -> None:
    batch = a_batch()
    assert not batch.is_tested
    assert not batch.is_pure_enough
    assert batch.hold_reason(at("2025-04-08 09:00")) == "no purity reading yet"


def test_a_batch_under_the_purity_floor_is_held() -> None:
    batch = a_batch().with_purity(Decimal("87.4"))
    assert batch.is_tested
    assert not batch.is_pure_enough
    assert batch.hold_reason(at("2025-04-08 09:00")) == "purity under the floor for this kit"


def test_a_batch_over_the_floor_is_free_to_draw_from() -> None:
    batch = a_batch().with_purity(Decimal("96.2"))
    assert batch.is_pure_enough
    assert batch.hold_reason(at("2025-04-08 09:00")) is None


def test_a_batch_past_its_expiry_is_held_even_when_it_was_pure() -> None:
    batch = a_batch().with_purity(Decimal("96.2"))
    assert batch.hold_reason(at("2025-04-08 14:00")) == "past its expiry"
    assert batch.hold_reason(at("2025-04-08 07:00")) == "not made yet"


def test_a_purity_reading_is_a_percentage() -> None:
    with pytest.raises(ValidationError, match="a percentage"):
        a_batch(rcp=Decimal("104"))


def test_the_colloid_floor_is_higher_than_the_bone_agent() -> None:
    colloid = a_batch(
        code="SC",
        activity=Activity.of(50, "mci"),
        volume=Volume.of(3),
        eluate_volume=Volume.of("0.6"),
    )
    assert not colloid.with_purity(Decimal("91")).is_pure_enough
    assert a_batch().with_purity(Decimal("91")).is_pure_enough


def test_saline_makes_up_the_rest_of_the_vial() -> None:
    batch = a_batch()
    assert batch.saline == Volume.of("2.5")
    assert batch.concentration.format() == "50.000 mCi/mL"


def test_a_vial_with_no_eluate_in_it_is_refused() -> None:
    with pytest.raises(ValidationError, match="no eluate in it"):
        a_batch(eluate_volume=Volume.zero())


def test_more_eluate_than_the_vial_holds_is_refused() -> None:
    with pytest.raises(ValidationError, match="more eluate went in"):
        a_batch(eluate_volume=Volume.of(8))


def test_a_vial_made_up_of_nothing_but_eluate_has_no_saline() -> None:
    assert a_batch(eluate_volume=Volume.of(6)).saline == Volume.zero()
