import datetime as dt

import pytest

from molycow.errors import ValidationError
from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
from molycow.units import Activity

INSTALLED = dt.date(2023, 6, 12)
CALIBRATED = dt.date(2025, 2, 3)


def an_instrument(**changed: object) -> Instrument:
    fields: dict[str, object] = {
        "id": "IC-0003",
        "kind": InstrumentKind.DOSE_CALIBRATOR,
        "maker": "Vernay",
        "model": "CRC-55tR",
        "serial": "551-40922",
        "installed_on": INSTALLED,
        "calibrated_on": CALIBRATED,
    }
    fields.update(changed)
    return Instrument(**fields)  # type: ignore[arg-type]


def a_source(**changed: object) -> CheckSource:
    fields: dict[str, object] = {
        "serial": "CS-9912",
        "symbol": "Cs-137",
        "certified_activity": Activity.of(200, "uci"),
        "certified_on": dt.date(2019, 7, 1),
    }
    fields.update(changed)
    return CheckSource(**fields)  # type: ignore[arg-type]


def test_the_annual_calibration_runs_a_year() -> None:
    calibrator = an_instrument()
    assert calibrator.calibration_due == dt.date(2026, 2, 3)
    assert calibrator.is_in_calibration(dt.date(2025, 4, 8))
    assert not calibrator.is_in_calibration(dt.date(2026, 2, 3))
    assert not calibrator.is_in_calibration(dt.date(2025, 1, 1))


def test_an_instrument_out_of_calibration_says_so() -> None:
    calibrator = an_instrument()
    assert calibrator.unusable_reason(dt.date(2025, 4, 8)) is None
    assert calibrator.unusable_reason(dt.date(2026, 6, 1)) == "annual calibration has run out"
    assert calibrator.unusable_reason(dt.date(2022, 1, 1)) == "not in service that day"


def test_a_retired_instrument_is_out_of_service() -> None:
    retired = an_instrument(retired_on=dt.date(2025, 5, 30))
    assert retired.is_in_service(dt.date(2025, 5, 30))
    assert not retired.is_in_service(dt.date(2025, 6, 1))
    assert not retired.is_usable_on(dt.date(2025, 6, 1))


def test_an_instrument_needs_a_serial_and_sensible_dates() -> None:
    with pytest.raises(ValidationError, match="serial number"):
        an_instrument(serial=" ")
    with pytest.raises(ValidationError, match="calibrated before it was installed"):
        an_instrument(calibrated_on=dt.date(2020, 1, 1))
    with pytest.raises(ValidationError, match="retired before it arrived"):
        an_instrument(retired_on=dt.date(2020, 1, 1))


def test_which_instruments_are_checked_every_morning() -> None:
    assert InstrumentKind.DOSE_CALIBRATOR.needs_daily_check
    assert InstrumentKind.SURVEY_METER.needs_daily_check
    assert not InstrumentKind.WELL_COUNTER.needs_daily_check


def test_an_instrument_prints_as_the_thing_on_the_bench() -> None:
    assert str(an_instrument()) == "Vernay CRC-55tR (551-40922)"


def test_a_check_source_decays_from_its_certificate() -> None:
    source = a_source()
    assert source.activity_on(dt.date(2019, 7, 1)) == Activity.of(200, "uci")
    reading = source.activity_on(dt.date(2025, 4, 8))
    assert reading < Activity.of(200, "uci")
    assert reading > Activity.of(150, "uci")


def test_a_source_has_no_reading_before_it_was_certified() -> None:
    with pytest.raises(ValidationError, match="before it was certified"):
        a_source().activity_on(dt.date(2019, 1, 1))


def test_only_a_sealed_nuclide_can_be_a_check_source() -> None:
    with pytest.raises(ValidationError, match="not a sealed check source"):
        a_source(symbol="Tc-99m")
    assert a_source(symbol="co57").symbol == "Co-57"


def test_a_check_source_needs_an_activity_and_a_serial() -> None:
    with pytest.raises(ValidationError, match="certified activity"):
        a_source(certified_activity=Activity.zero())
    with pytest.raises(ValidationError, match="needs its serial"):
        a_source(serial="  ")


def test_a_retired_source_is_out_of_use() -> None:
    source = a_source(retired_on=dt.date(2025, 3, 31))
    assert source.is_in_use_on(dt.date(2025, 3, 31))
    assert not source.is_in_use_on(dt.date(2025, 4, 1))
    assert not source.is_in_use_on(dt.date(2019, 1, 1))


def test_a_short_lived_source_falls_much_further_in_the_same_time() -> None:
    caesium = a_source().activity_on(dt.date(2025, 4, 8))
    cobalt = a_source(symbol="Co-57", serial="CO-2201").activity_on(dt.date(2025, 4, 8))
    assert cobalt < caesium
