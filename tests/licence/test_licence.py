from decimal import Decimal

import pytest

from molycow.errors import NotFoundError, ValidationError
from molycow.model.licence import PossessionLimit
from molycow.store import Book
from molycow.store.licence import LicenceRepository
from molycow.units import Activity


def a_limit(**changed: object) -> PossessionLimit:
    fields: dict[str, object] = {
        "symbol": "Tc-99m",
        "limit": Activity.of(20, "ci"),
        "note": "eluate, batches and drawn doses",
    }
    fields.update(changed)
    return PossessionLimit(**fields)  # type: ignore[arg-type]


def test_a_limit_says_whether_a_holding_fits_under_it() -> None:
    limit = a_limit()
    assert limit.allows(Activity.of(15, "ci"))
    assert limit.allows(Activity.of(20, "ci"))
    assert not limit.allows(Activity.of("20.5", "ci"))


def test_the_headroom_runs_out_at_the_limit() -> None:
    limit = a_limit()
    assert limit.headroom(Activity.of(15, "ci")).format("ci", 1) == "5.0 Ci"
    assert limit.headroom(Activity.of(25, "ci")).is_zero()


def test_the_share_of_the_licence_in_use() -> None:
    assert a_limit().share_used(Activity.of(5, "ci")) == Decimal("0.25")


def test_a_limit_of_nothing_is_not_a_limit() -> None:
    with pytest.raises(ValidationError, match="not a limit"):
        a_limit(limit=Activity.zero())


def test_a_limit_names_a_nuclide_the_pharmacy_handles() -> None:
    with pytest.raises(ValidationError, match="does not handle"):
        a_limit(symbol="Pu-239")
    assert a_limit(symbol="tc99m").symbol == "Tc-99m"


def test_a_limit_prints_in_curies() -> None:
    assert a_limit().format() == "Tc-99m 20.0 Ci"


def test_the_licence_arrives_with_the_book(book: Book) -> None:
    repo = LicenceRepository(book)
    assert "Tc-99m" in repo.names()
    assert "Mo-99" in repo.names()
    assert repo.get("I-131").limit == Activity.of(5, "ci")


def test_a_nuclide_the_licence_does_not_name(book: Book) -> None:
    repo = LicenceRepository(book)
    assert repo.find("Y-90") is None
    with pytest.raises(NotFoundError, match="does not name that nuclide"):
        repo.get("Y-90")


def test_an_amendment_changes_a_ceiling(book: Book) -> None:
    repo = LicenceRepository(book)
    repo.set_limit("I-131", 12, "therapy programme widened")
    assert repo.get("I-131").limit == Activity.of(12, "ci")
    assert repo.get("I-131").note == "therapy programme widened"


def test_an_amendment_can_add_a_nuclide(book: Book) -> None:
    repo = LicenceRepository(book)
    repo.set_limit("Y-90", 1, "microsphere programme")
    assert "Y-90" in repo.names()
    assert repo.get("Y-90").limit == Activity.of(1, "ci")


def test_every_limit_on_the_licence_reads_back(book: Book) -> None:
    for limit in LicenceRepository(book).all():
        assert limit.limit.uci > 0
        assert limit.note.strip()
