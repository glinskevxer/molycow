import datetime as dt

import pytest
from tests.conftest import at
from tests.support import a_customer

from molycow.errors import ConflictError, NotFoundError, ValidationError
from molycow.model.route import Route, Run
from molycow.store import Book
from molycow.store.routes import RouteRepository, RunRepository

DAY = dt.date(2025, 4, 8)


def a_route(route_id: str = "RT-0001", **changed: object) -> Route:
    fields: dict[str, object] = {
        "id": route_id,
        "name": f"north morning {route_id[-4:]}",
        "zone": "north",
        "stops": ("CU-0001",),
        "leaves_at": dt.time(6, 30),
    }
    fields.update(changed)
    return Route(**fields)  # type: ignore[arg-type]


def test_a_route_needs_a_name_and_stops() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        a_route(name=" ")
    with pytest.raises(ValidationError, match="no stops"):
        a_route(stops=())
    with pytest.raises(ValidationError, match="each stop once"):
        a_route(stops=("CU-0001", "CU-0001"))


def test_a_route_knows_where_a_stop_falls() -> None:
    route = a_route(stops=("CU-0002", "CU-0001"))
    assert route.position_of("CU-0001") == 2
    assert route.stop_count == 2
    with pytest.raises(ValidationError, match="not on this route"):
        route.position_of("CU-0009")


def test_a_route_goes_in_with_its_stops_in_order(book: Book) -> None:
    a_customer(book)
    a_customer(book, id="CU-0002", name="Halvern Clinic", zone="north")
    repo = RouteRepository(book)
    repo.add(a_route(stops=("CU-0002", "CU-0001")))
    back = repo.get("RT-0001")
    assert back.stops == ("CU-0002", "CU-0001")
    assert back.leaves_at == dt.time(6, 30)


def test_routes_are_found_by_zone_and_by_stop(book: Book) -> None:
    a_customer(book)
    repo = RouteRepository(book)
    repo.add(a_route())
    repo.add(a_route("RT-0002", zone="river"))
    assert [one.id for one in repo.for_zone("north")] == ["RT-0001"]
    assert [one.id for one in repo.calling_at("CU-0001")] == ["RT-0001", "RT-0002"]
    assert repo.next_id() == "RT-0003"


def test_a_route_that_is_not_there(book: Book) -> None:
    repo = RouteRepository(book)
    assert repo.find("RT-0404") is None
    with pytest.raises(NotFoundError, match="no such route"):
        repo.get("RT-0404")


def test_a_run_is_one_day_of_a_route(book: Book) -> None:
    a_customer(book)
    RouteRepository(book).add(a_route())
    runs = RunRepository(book)
    runs.add(Run("RT-0001", DAY, "J. Fennimore"))
    back = runs.get("RT-0001", DAY)
    assert not back.has_left
    assert back.driver == "J. Fennimore"


def test_the_same_route_cannot_run_twice_on_one_day(book: Book) -> None:
    a_customer(book)
    RouteRepository(book).add(a_route())
    runs = RunRepository(book)
    runs.add(Run("RT-0001", DAY, "J. Fennimore"))
    with pytest.raises(ConflictError):
        runs.add(Run("RT-0001", DAY, "Someone Else"))


def test_a_run_leaves_and_comes_back(book: Book) -> None:
    a_customer(book)
    RouteRepository(book).add(a_route())
    runs = RunRepository(book)
    run = runs.add(Run("RT-0001", DAY, "J. Fennimore"))
    runs.save(run.leaving(at("2025-04-08 06:35")))
    assert runs.get("RT-0001", DAY).has_left
    runs.save(runs.get("RT-0001", DAY).back(at("2025-04-08 09:40")))
    assert runs.get("RT-0001", DAY).is_back


def test_a_run_cannot_come_back_before_it_left() -> None:
    run = Run("RT-0001", DAY, "J. Fennimore")
    with pytest.raises(ValidationError, match="has not left yet"):
        run.back(at("2025-04-08 09:40"))
    left = run.leaving(at("2025-04-08 06:35"))
    with pytest.raises(ValidationError, match="already left"):
        left.leaving(at("2025-04-08 07:00"))
    with pytest.raises(ValidationError, match="came back before it left"):
        Run("RT-0001", DAY, "J. F", at("2025-04-08 09:00"), at("2025-04-08 06:00"))


def test_a_run_that_is_not_there(book: Book) -> None:
    runs = RunRepository(book)
    assert runs.find("RT-0001", DAY) is None
    with pytest.raises(NotFoundError, match="no such run"):
        runs.get("RT-0001", DAY)
    assert runs.on_day(DAY) == []


def test_a_run_needs_a_driver() -> None:
    with pytest.raises(ValidationError, match="needs a driver"):
        Run("RT-0001", DAY, "  ")
