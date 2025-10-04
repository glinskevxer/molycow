import datetime as dt

import pytest
from tests.conftest import at

from molycow.errors import ValidationError
from molycow.model.waste import HALF_LIVES_HELD, Container, ContainerKind, WasteItem
from molycow.units import Activity

OPENED = at("2025-04-08 06:00")


def an_item(**changed: object) -> WasteItem:
    fields: dict[str, object] = {
        "symbol": "Tc-99m",
        "activity": Activity.of(40, "mci"),
        "added_at": at("2025-04-08 10:30"),
        "source": "DS-250408-14",
    }
    fields.update(changed)
    return WasteItem(**fields)  # type: ignore[arg-type]


def a_container(**changed: object) -> Container:
    fields: dict[str, object] = {
        "id": "WC-0042",
        "kind": ContainerKind.VIALS,
        "opened_at": OPENED,
        "items": (an_item(),),
    }
    fields.update(changed)
    return Container(**fields)  # type: ignore[arg-type]


def test_a_container_is_held_ten_half_lives() -> None:
    assert HALF_LIVES_HELD == 10
    item = an_item()
    held_hours = (item.clear_at - item.added_at).total_seconds() / 3600
    assert round(held_hours, 2) == 60.07


def test_a_technetium_container_clears_in_days_and_an_iodine_one_in_months() -> None:
    technetium = a_container()
    iodine = a_container(items=(an_item(symbol="I-131", activity=Activity.of(5, "mci")),))
    assert technetium.clear_at is not None
    assert iodine.clear_at is not None
    assert iodine.clear_at - technetium.clear_at > dt.timedelta(days=70)


def test_the_container_takes_the_longest_lived_thing_in_it() -> None:
    mixed = a_container(
        items=(
            an_item(),
            an_item(symbol="I-131", activity=Activity.of(2, "mci")),
        )
    )
    longest = mixed.longest_lived
    assert longest is not None
    assert longest.symbol == "I-131"
    assert mixed.clear_at == mixed.items[1].clear_at


def test_the_activity_in_a_container_falls_as_it_sits() -> None:
    container = a_container()
    assert container.activity_at(at("2025-04-08 10:30")).format() == "40.000 mCi"
    assert container.activity_at(at("2025-04-09 10:30")).format("mci", 2) == "2.51 mCi"
    assert container.activity_at(OPENED).is_zero()


def test_an_empty_container_has_nothing_to_say() -> None:
    empty = a_container(items=())
    assert empty.clear_at is None
    assert empty.longest_lived is None
    assert empty.hold_reason(at("2025-04-20 09:00")) == "nothing has gone in it"


def test_an_open_container_is_held_whatever_the_clock_says() -> None:
    container = a_container()
    assert container.hold_reason(at("2025-05-20 09:00")) == "still open"


def test_a_closed_container_is_held_until_its_ten_half_lives() -> None:
    closed = a_container().closed(at("2025-04-08 17:00"))
    assert closed.hold_reason(at("2025-04-09 09:00")) == "not held ten half lives yet"
    assert closed.hold_reason(at("2025-04-12 09:00")) is None
    assert closed.is_held_long_enough(at("2025-04-12 09:00"))


def test_nothing_goes_into_a_closed_container() -> None:
    closed = a_container().closed(at("2025-04-08 17:00"))
    with pytest.raises(ValidationError, match="is closed"):
        closed.with_item(an_item())
    with pytest.raises(ValidationError, match="already closed"):
        closed.closed(at("2025-04-08 18:00"))


def test_an_empty_container_is_not_closed_it_is_unused() -> None:
    with pytest.raises(ValidationError, match="unused"):
        a_container(items=()).closed(at("2025-04-08 17:00"))


def test_something_cannot_go_in_before_the_container_was_opened() -> None:
    with pytest.raises(ValidationError, match="before the container was opened"):
        a_container(items=(an_item(added_at=at("2025-04-07 10:30")),))


def test_a_container_is_closed_before_it_is_disposed_of() -> None:
    with pytest.raises(ValidationError, match="closed before it is disposed"):
        a_container(disposed_at=at("2025-04-20 09:00"))
    with pytest.raises(ValidationError, match="closed before it was opened"):
        a_container(closed_at=at("2025-04-07 09:00"))


def test_an_item_says_what_it_is_and_where_it_came_from() -> None:
    with pytest.raises(ValidationError, match="no activity"):
        an_item(activity=Activity.zero())
    with pytest.raises(ValidationError, match="where it came from"):
        an_item(source=" ")
    with pytest.raises(ValidationError, match="does not handle"):
        an_item(symbol="Pu-239")


def test_adding_an_item_gives_back_a_fuller_container() -> None:
    fuller = a_container().with_item(an_item(source="DS-250408-15"))
    assert len(fuller.items) == 2
    assert fuller.activity_at(at("2025-04-08 10:30")).format() == "80.000 mCi"


def test_a_sharps_container_knows_what_it_is_for() -> None:
    assert ContainerKind.SHARPS.takes_sharps
    assert not ContainerKind.VIALS.takes_sharps
