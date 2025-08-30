from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.survey import (
    WIPE_LIMIT_DPM,
    Area,
    DoseRate,
    Survey,
    Wipe,
)

WALKED = at("2025-04-08 17:40")


def a_wipe(**changed: object) -> Wipe:
    fields: dict[str, object] = {
        "area": Area.HOT_LAB,
        "spot": "draw station bench top",
        "counts": 340,
        "background": 120,
        "efficiency": Decimal("0.35"),
    }
    fields.update(changed)
    return Wipe(**fields)  # type: ignore[arg-type]


def a_survey(**changed: object) -> Survey:
    fields: dict[str, object] = {
        "id": "SV-250408-02",
        "at": WALKED,
        "surveyed_by": "K. Ruzicka",
        "readings": (
            (Area.HOT_LAB, DoseRate.of("1.2")),
            (Area.RECEPTION, DoseRate.of("0.01")),
        ),
        "wipes": (a_wipe(),),
    }
    fields.update(changed)
    return Survey(**fields)  # type: ignore[arg-type]


def test_the_public_side_of_the_building_is_held_much_tighter() -> None:
    assert Area.RECEPTION.dose_rate_limit == Decimal("0.05")
    assert Area.HOT_LAB.dose_rate_limit == Decimal(5)
    assert Area.HOT_LAB.is_restricted
    assert not Area.DOCK.is_restricted


def test_a_dose_rate_prints_in_the_units_the_meter_reads() -> None:
    assert str(DoseRate.of("1.234")) == "1.23 mrem/h"
    assert DoseRate.of(6).over(Area.HOT_LAB.dose_rate_limit)
    assert not DoseRate.of(4).over(Area.HOT_LAB.dose_rate_limit)


def test_a_negative_dose_rate_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        DoseRate.of(-1)


def test_a_wipe_is_counted_net_of_background_and_divided_by_efficiency() -> None:
    wipe = a_wipe()
    assert wipe.net_counts == 220
    assert wipe.dpm == Decimal(629)
    assert wipe.is_clean()


def test_a_wipe_under_background_reads_as_nothing() -> None:
    assert a_wipe(counts=80).dpm == Decimal(0)


def test_a_dirty_wipe_is_over_the_limit() -> None:
    wipe = a_wipe(counts=1200)
    assert wipe.dpm > WIPE_LIMIT_DPM
    assert not wipe.is_clean()


def test_a_poor_counter_efficiency_makes_the_same_counts_worse() -> None:
    keen = a_wipe(efficiency=Decimal("0.80")).dpm
    poor = a_wipe(efficiency=Decimal("0.10")).dpm
    assert poor > keen


def test_an_efficiency_that_is_not_a_fraction_is_refused() -> None:
    with pytest.raises(ValidationError, match="fraction of one"):
        a_wipe(efficiency=Decimal("1.4"))
    with pytest.raises(ValidationError, match="fraction of one"):
        a_wipe(efficiency=Decimal(0))


def test_a_wipe_names_where_it_came_from() -> None:
    with pytest.raises(ValidationError, match="names the spot"):
        a_wipe(spot=" ")
    with pytest.raises(ValidationError, match="cannot be negative"):
        a_wipe(counts=-4)


def test_a_clean_survey_passes_with_nothing_to_report() -> None:
    survey = a_survey()
    assert survey.passes()
    assert survey.failure() is None
    assert survey.hot_areas() == []
    assert survey.dirty_wipes() == []


def test_a_hot_area_is_named_first_in_the_failure() -> None:
    survey = a_survey(
        readings=((Area.HOT_LAB, DoseRate.of("7.5")), (Area.RECEPTION, DoseRate.of("0.01")))
    )
    assert not survey.passes()
    assert survey.failure() == "hot lab reading 7.50 mrem/h"


def test_the_public_side_fails_on_a_reading_the_hot_lab_would_shrug_at() -> None:
    survey = a_survey(readings=((Area.RECEPTION, DoseRate.of("0.4")),))
    assert not survey.passes()
    assert survey.failure() == "reception reading 0.40 mrem/h"


def test_a_dirty_wipe_fails_a_survey_that_read_cool() -> None:
    survey = a_survey(wipes=(a_wipe(counts=2000),))
    assert not survey.passes()
    failure = survey.failure()
    assert failure is not None
    assert failure.startswith("draw station bench top wiped")


def test_the_worst_reading_is_the_one_that_gets_talked_about() -> None:
    worst = a_survey().worst_reading
    assert worst is not None
    assert worst.mrem_per_hour == Decimal("1.2")
    assert a_survey(readings=(), wipes=(a_wipe(),)).worst_reading is None


def test_a_survey_with_nothing_in_it_is_refused() -> None:
    with pytest.raises(ValidationError, match="no readings"):
        a_survey(readings=(), wipes=())
    with pytest.raises(ValidationError, match="signed by"):
        a_survey(surveyed_by="")
