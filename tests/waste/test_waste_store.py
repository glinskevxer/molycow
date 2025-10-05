from decimal import Decimal

import pytest
from tests.conftest import at

from molycow.errors import ConflictError, NotFoundError, ValidationError
from molycow.model.waste import Container, ContainerKind, WasteItem
from molycow.store import Book
from molycow.store.waste import ContainerRepository
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


def a_container(container_id: str = "WC-0042", **changed: object) -> Container:
    fields: dict[str, object] = {
        "id": container_id,
        "kind": ContainerKind.VIALS,
        "opened_at": OPENED,
        "items": (),
    }
    fields.update(changed)
    return Container(**fields)  # type: ignore[arg-type]


def test_a_container_goes_in_and_comes_back(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    assert repo.get("WC-0042").kind is ContainerKind.VIALS
    assert repo.next_id() == "WC-0043"


def test_items_go_in_one_at_a_time(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    repo.add_item("WC-0042", an_item())
    repo.add_item("WC-0042", an_item(source="DS-250408-15", activity=Activity.of(12, "mci")))
    back = repo.get("WC-0042")
    assert len(back.items) == 2
    assert back.activity_at(at("2025-04-08 10:30")).format() == "52.000 mCi"


def test_the_same_thing_cannot_go_in_twice(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    repo.add_item("WC-0042", an_item())
    with pytest.raises(ConflictError):
        repo.add_item("WC-0042", an_item())


def test_nothing_goes_into_a_closed_container(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    repo.add_item("WC-0042", an_item())
    repo.close("WC-0042", at("2025-04-08 17:00"))
    with pytest.raises(ValidationError, match="is closed"):
        repo.add_item("WC-0042", an_item(source="DS-250408-15"))


def test_open_and_stored_containers_are_different_lists(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    repo.add(a_container("WC-0043", kind=ContainerKind.SHARPS))
    repo.add_item("WC-0042", an_item())
    repo.close("WC-0042", at("2025-04-08 17:00"))
    assert [one.id for one in repo.open_containers()] == ["WC-0043"]
    assert [one.id for one in repo.in_storage()] == ["WC-0042"]
    assert [one.id for one in repo.open_containers(ContainerKind.SHARPS)] == ["WC-0043"]


def test_disposing_writes_the_survey_and_the_signature(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    repo.add_item("WC-0042", an_item())
    repo.close("WC-0042", at("2025-04-08 17:00"))
    repo.dispose("WC-0042", at("2025-04-12 09:00"), "K. Ruzicka", Decimal("0.01"))
    assert repo.get("WC-0042").is_disposed
    assert repo.disposal_survey("WC-0042") == Decimal("0.01")
    assert repo.disposed_by("WC-0042") == "K. Ruzicka"
    assert repo.in_storage() == []


def test_an_undisposed_container_has_no_survey_on_it(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    assert repo.disposal_survey("WC-0042") is None
    assert repo.disposed_by("WC-0042") is None
    assert repo.disposal_survey("WC-0099") is None


def test_a_container_that_is_not_there(book: Book) -> None:
    repo = ContainerRepository(book)
    assert repo.find("WC-0099") is None
    with pytest.raises(NotFoundError, match="no such container"):
        repo.get("WC-0099")


def test_the_items_keep_their_own_nuclides(book: Book) -> None:
    repo = ContainerRepository(book)
    repo.add(a_container())
    repo.add_item("WC-0042", an_item())
    repo.add_item("WC-0042", an_item(symbol="I-131", source="DS-250408-20"))
    longest = repo.get("WC-0042").longest_lived
    assert longest is not None
    assert longest.symbol == "I-131"
