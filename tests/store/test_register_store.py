import datetime as dt

import pytest

from molycow.errors import ConflictError, NotFoundError
from molycow.model import AuthorizedUser, Customer, CustomerKind
from molycow.store import Book
from molycow.store.register import AuthorizedUserRepository, CustomerRepository

OPENED = dt.date(2025, 1, 6)


def a_customer(customer_id: str = "CU-0001", **changed: object) -> Customer:
    fields: dict[str, object] = {
        "id": customer_id,
        "name": "Saint Brannon Medical Centre",
        "kind": CustomerKind.HOSPITAL,
        "licence": "42-28931-01",
        "street": "1400 Weir Street",
        "town": "Ardmore",
        "zone": "north",
        "opened_on": OPENED,
    }
    fields.update(changed)
    return Customer(**fields)  # type: ignore[arg-type]


def a_user(user_id: str = "AU-0004", **changed: object) -> AuthorizedUser:
    fields: dict[str, object] = {
        "id": user_id,
        "customer_id": "CU-0001",
        "name": "R. Okonkwo",
        "licence": "42-28931-01",
        "added_on": OPENED,
        "nuclides": frozenset({"Tc-99m", "I-131"}),
    }
    fields.update(changed)
    return AuthorizedUser(**fields)  # type: ignore[arg-type]


def test_a_customer_goes_in_and_comes_back_the_same(book: Book) -> None:
    repo = CustomerRepository(book)
    repo.add(a_customer())
    assert repo.get("CU-0001") == a_customer()


def test_a_customer_that_is_not_there(book: Book) -> None:
    repo = CustomerRepository(book)
    assert repo.find("CU-0404") is None
    with pytest.raises(NotFoundError, match="no such customer"):
        repo.get("CU-0404")


def test_the_same_customer_twice_is_a_conflict(book: Book) -> None:
    repo = CustomerRepository(book)
    repo.add(a_customer())
    with pytest.raises(ConflictError):
        repo.add(a_customer())


def test_two_customers_cannot_share_a_name(book: Book) -> None:
    repo = CustomerRepository(book)
    repo.add(a_customer())
    with pytest.raises(ConflictError):
        repo.add(a_customer("CU-0002"))


def test_a_customer_is_found_by_name(book: Book) -> None:
    repo = CustomerRepository(book)
    repo.add(a_customer())
    assert repo.by_name("Saint Brannon Medical Centre").id == "CU-0001"
    with pytest.raises(NotFoundError, match="no customer by that name"):
        repo.by_name("Nowhere General")


def test_customers_list_by_zone_and_by_day(book: Book) -> None:
    repo = CustomerRepository(book)
    repo.add(a_customer())
    repo.add(a_customer("CU-0002", name="Halvern Clinic", zone="river"))
    repo.add(a_customer("CU-0003", name="Old Mill Imaging", closed_on=dt.date(2025, 3, 31)))
    assert [one.id for one in repo.all()] == ["CU-0001", "CU-0002", "CU-0003"]
    assert [one.id for one in repo.all(zone="north")] == ["CU-0001", "CU-0003"]
    assert [one.id for one in repo.all(open_on=dt.date(2025, 4, 8))] == ["CU-0001", "CU-0002"]
    assert repo.count() == 3


def test_closing_a_customer_keeps_the_record(book: Book) -> None:
    repo = CustomerRepository(book)
    repo.add(a_customer())
    closed = repo.close("CU-0001", dt.date(2025, 6, 30))
    assert closed.closed_on == dt.date(2025, 6, 30)
    assert repo.get("CU-0001").closed_on == dt.date(2025, 6, 30)
    assert repo.count() == 1


def test_closing_a_customer_that_is_not_there(book: Book) -> None:
    with pytest.raises(NotFoundError):
        CustomerRepository(book).close("CU-0404", dt.date(2025, 6, 30))


def test_an_authorized_user_keeps_the_nuclides_named_on_it(book: Book) -> None:
    CustomerRepository(book).add(a_customer())
    users = AuthorizedUserRepository(book)
    users.add(a_user())
    back = users.get("AU-0004")
    assert back.may_order("Tc-99m")
    assert back.may_order("I-131")
    assert not back.may_order("Lu-177")


def test_a_user_without_a_customer_is_refused(book: Book) -> None:
    users = AuthorizedUserRepository(book)
    with pytest.raises(Exception, match="not there"):
        users.add(a_user())


def test_users_list_for_a_customer_and_a_day(book: Book) -> None:
    CustomerRepository(book).add(a_customer())
    users = AuthorizedUserRepository(book)
    users.add(a_user())
    users.add(a_user("AU-0005", name="P. Vantrease", ended_on=dt.date(2025, 2, 28)))
    assert [one.id for one in users.for_customer("CU-0001")] == ["AU-0004", "AU-0005"]
    current = users.for_customer("CU-0001", on=dt.date(2025, 4, 8))
    assert [one.id for one in current] == ["AU-0004"]


def test_a_user_can_be_named_for_more_nuclides(book: Book) -> None:
    CustomerRepository(book).add(a_customer())
    users = AuthorizedUserRepository(book)
    users.add(a_user())
    widened = users.set_nuclides("AU-0004", ["Tc-99m", "Lu-177"])
    assert widened.may_order("Lu-177")
    assert not users.get("AU-0004").may_order("I-131")


def test_ending_a_user_leaves_them_readable(book: Book) -> None:
    CustomerRepository(book).add(a_customer())
    users = AuthorizedUserRepository(book)
    users.add(a_user())
    users.end("AU-0004", dt.date(2025, 5, 1))
    assert users.get("AU-0004").ended_on == dt.date(2025, 5, 1)
    assert users.name_of("AU-0004") == "R. Okonkwo"
    assert users.licence_of("AU-0004") == "42-28931-01"


def test_a_user_who_is_not_there(book: Book) -> None:
    users = AuthorizedUserRepository(book)
    assert users.find("AU-0404") is None
    assert users.licence_of("AU-0404") is None
    with pytest.raises(NotFoundError, match="no such authorized user"):
        users.name_of("AU-0404")
