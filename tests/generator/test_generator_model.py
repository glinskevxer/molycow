import datetime as dt
from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.generator import ELUATE_HOURS, Elution, Generator
from molycow.units import Activity, Volume

CALIBRATED = at("2025-04-05 12:00")


def a_generator(**changed: object) -> Generator:
    fields: dict[str, object] = {
        "id": "GEN-0027",
        "serial": "M99-44182",
        "maker": "Corren Isotopes",
        "calibrated_at": CALIBRATED,
        "calibrated_activity": Activity.of(2, "Ci"),
        "received_on": dt.date(2025, 4, 5),
        "expires_on": dt.date(2025, 4, 19),
    }
    fields.update(changed)
    return Generator(**fields)  # type: ignore[arg-type]


def an_elution(**changed: object) -> Elution:
    fields: dict[str, object] = {
        "id": "EL-250408-01",
        "generator_id": "GEN-0027",
        "drawn_at": at("2025-04-08 06:30"),
        "volume": Volume.of(10),
        "activity": Activity.of(940, "mCi"),
        "expected": Activity.of(1000, "mCi"),
    }
    fields.update(changed)
    return Elution(**fields)  # type: ignore[arg-type]


def test_the_parent_decays_from_the_makers_calibration() -> None:
    column = a_generator()
    assert column.parent_at(CALIBRATED).format("ci", 3) == "2.000 Ci"
    later = column.parent_at(at("2025-04-08 12:00"))
    assert later.format("mci", 0) == "939 mCi"


def test_a_generator_needs_a_serial_and_a_calibration() -> None:
    with pytest.raises(ValidationError, match="maker's serial"):
        a_generator(serial="  ")
    with pytest.raises(ValidationError, match="no calibration"):
        a_generator(calibrated_activity=Activity.zero())


def test_a_generator_cannot_expire_before_it_arrived() -> None:
    with pytest.raises(ValidationError, match="expires before it arrived"):
        a_generator(expires_on=dt.date(2025, 4, 4))


def test_a_generator_cannot_be_retired_before_it_arrived() -> None:
    with pytest.raises(ValidationError, match="retired before it arrived"):
        a_generator(retired_on=dt.date(2025, 4, 1))


def test_a_generator_is_in_date_between_arrival_and_expiry() -> None:
    column = a_generator()
    assert not column.is_in_date(dt.date(2025, 4, 4))
    assert column.is_in_date(dt.date(2025, 4, 5))
    assert column.is_in_date(dt.date(2025, 4, 19))
    assert not column.is_in_date(dt.date(2025, 4, 20))


def test_a_retired_generator_is_out_of_use_from_that_day() -> None:
    column = a_generator(retired_on=dt.date(2025, 4, 12))
    assert column.is_in_date(dt.date(2025, 4, 12))
    assert not column.is_in_date(dt.date(2025, 4, 13))
    assert column.age_days(dt.date(2025, 4, 12)) == 7


def test_a_column_never_milked_is_worked_from_the_calibration() -> None:
    column = a_generator()
    first = column.expectation_at(None, at("2025-04-08 06:30"))
    assert first.format("mci", 0) == "960 mCi"


def test_a_column_milked_yesterday_gives_less_this_morning() -> None:
    column = a_generator()
    yesterday = column.expectation_at(None, at("2025-04-07 06:30"))
    today = column.expectation_at(at("2025-04-07 06:30"), at("2025-04-08 06:30"))
    assert today < yesterday


def test_an_eluate_is_good_for_twelve_hours() -> None:
    elution = an_elution()
    assert ELUATE_HOURS == 12
    assert elution.expires_at == at("2025-04-08 18:30")
    assert elution.is_in_date_at(at("2025-04-08 18:00"))
    assert not elution.is_in_date_at(at("2025-04-08 18:31"))
    assert not elution.is_in_date_at(at("2025-04-08 06:29"))


def test_an_eluate_has_a_concentration_that_falls_through_the_day() -> None:
    elution = an_elution()
    assert elution.concentration.format() == "94.000 mCi/mL"
    later = elution.concentration_at(at("2025-04-08 12:30"))
    assert later.format() == "47.036 mCi/mL"


def test_an_eluate_has_no_activity_before_it_was_drawn() -> None:
    with pytest.raises(ValidationError, match="before it was drawn"):
        an_elution().activity_at(at("2025-04-08 06:00"))


def test_the_efficiency_is_what_came_off_against_what_was_there() -> None:
    assert an_elution().efficiency.quantize(Decimal("0.01")) == Decimal("0.94")


def test_an_elution_that_expected_nothing_cannot_report_efficiency() -> None:
    empty = an_elution(expected=Activity.zero())
    with pytest.raises(ValidationError, match="nothing was expected"):
        assert empty.efficiency


def test_an_elution_needs_volume_and_activity() -> None:
    with pytest.raises(ValidationError, match="no volume"):
        an_elution(volume=Volume.zero())
    with pytest.raises(ValidationError, match="something in it"):
        an_elution(activity=Activity.zero())


def test_no_elution_vial_holds_more_than_thirty_millilitres() -> None:
    with pytest.raises(ValidationError, match="holds that much"):
        an_elution(volume=Volume.of(35))


def test_hours_since_an_elution() -> None:
    assert an_elution().hours_since(at("2025-04-08 12:30")) == Decimal(6)
