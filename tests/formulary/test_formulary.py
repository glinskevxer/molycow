from decimal import Decimal

import pytest

from molycow.errors import ValidationError
from molycow.formulary import boiled, codes, formula, is_known, known
from molycow.units import Activity, Volume


def test_a_kit_is_looked_up_by_the_code_on_the_box() -> None:
    mdp = formula("MDP")
    assert mdp.name == "medronate"
    assert mdp.nuclide == "Tc-99m"
    assert str(mdp) == "Tc-99m medronate"


def test_the_code_is_folded_before_it_is_looked_up() -> None:
    assert formula(" mdp ") is formula("MDP")
    assert is_known("sesta")
    assert not is_known("HIDA")


def test_a_kit_the_pharmacy_does_not_compound_is_refused() -> None:
    with pytest.raises(ValidationError, match="does not compound"):
        formula("HIDA")


def test_every_code_is_reachable_and_unique() -> None:
    assert len(set(codes())) == len(codes())
    for code in codes():
        assert formula(code).code == code


def test_an_activity_inside_the_insert_fits() -> None:
    mdp = formula("MDP")
    assert mdp.activity_fits(Activity.of(250, "mci"))
    assert mdp.activity_fits(Activity.of(100, "mci"))
    assert mdp.activity_fits(Activity.of(400, "mci"))
    assert not mdp.activity_fits(Activity.of(90, "mci"))
    assert not mdp.activity_fits(Activity.of(410, "mci"))


def test_a_volume_inside_the_insert_fits() -> None:
    sesta = formula("SESTA")
    assert sesta.volume_fits(Volume.of(2))
    assert not sesta.volume_fits(Volume.of("0.5"))
    assert not sesta.volume_fits(Volume.of(4))


def test_a_prep_outside_the_activity_range_is_refused_with_the_range() -> None:
    with pytest.raises(ValidationError) as caught:
        formula("SESTA").check(Activity.of(200, "mci"), Volume.of(2))
    assert caught.value.detail["allowed"] == "100.000 mCi to 150.000 mCi"


def test_a_prep_outside_the_volume_range_is_refused_with_the_range() -> None:
    with pytest.raises(ValidationError) as caught:
        formula("SESTA").check(Activity.of(120, "mci"), Volume.of(6))
    assert caught.value.detail["allowed"] == "1.000 mL to 3.000 mL"


def test_a_prep_inside_both_ranges_passes_quietly() -> None:
    formula("SESTA").check(Activity.of(120, "mci"), Volume.of(2))


def test_the_kits_that_go_in_the_heating_block() -> None:
    heated = {one.code for one in boiled()}
    assert heated == {"SESTA", "MAG3", "SC"}
    assert formula("SESTA").needs_incubation
    assert not formula("MDP").needs_incubation


def test_every_monograph_is_self_consistent() -> None:
    for one in known():
        assert one.min_activity < one.max_activity
        assert one.min_volume < one.max_volume
        assert one.shelf_hours > 0
        assert Decimal(80) <= one.rcp_floor <= Decimal(100)
        assert one.incubate_minutes >= 0


def test_the_colloid_is_held_to_a_higher_purity() -> None:
    assert formula("SC").rcp_floor == Decimal(92)
    assert formula("MDP").rcp_floor == Decimal(90)


def test_the_lung_kit_is_the_one_that_goes_in_the_fridge() -> None:
    assert formula("MAA").refrigerate
    assert not formula("MDP").refrigerate
