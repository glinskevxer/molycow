import datetime as dt

import pytest

from molycow.errors import ValidationError
from molycow.model import AuthorizedUser, Customer, CustomerKind
from molycow.model.register import check_licence, check_zone

OPENED = dt.date(2025, 1, 6)


def a_customer(**changed: object) -> Customer:
    fields: dict[str, object] = {
        "id": "CU-0001",
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


def a_user(**changed: object) -> AuthorizedUser:
    fields: dict[str, object] = {
        "id": "AU-0004",
        "customer_id": "CU-0001",
        "name": "R. Okonkwo",
        "licence": "42-28931-01",
        "added_on": OPENED,
        "nuclides": frozenset({"Tc-99m", "I-131"}),
    }
    fields.update(changed)
    return AuthorizedUser(**fields)  # type: ignore[arg-type]


def test_a_licence_number_has_a_shape() -> None:
    assert check_licence(" 42-28931-01 ") == "42-28931-01"
    with pytest.raises(ValidationError, match="reads like"):
        check_licence("42-28931")


def test_a_zone_is_one_of_the_routes() -> None:
    assert check_zone(" North ") == "north"
    with pytest.raises(ValidationError, match="not a delivery zone"):
        check_zone("west")


def test_a_customer_carries_its_address() -> None:
    assert a_customer().address == "1400 Weir Street, Ardmore"


def test_a_customer_needs_a_customer_number() -> None:
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_customer(id="AU-0001")


def test_a_customer_needs_a_name() -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        a_customer(name="   ")


def test_a_customer_cannot_close_before_it_opened() -> None:
    with pytest.raises(ValidationError, match="close before it opened"):
        a_customer(closed_on=OPENED - dt.timedelta(days=1))


def test_a_customer_is_open_between_its_dates() -> None:
    shut = a_customer(closed_on=dt.date(2025, 6, 30))
    assert not shut.is_open_on(dt.date(2025, 1, 5))
    assert shut.is_open_on(OPENED)
    assert shut.is_open_on(dt.date(2025, 6, 30))
    assert not shut.is_open_on(dt.date(2025, 7, 1))


def test_an_open_ended_customer_stays_open() -> None:
    assert a_customer().is_open_on(dt.date(2030, 1, 1))


def test_only_a_hospital_or_a_research_site_takes_therapy() -> None:
    assert a_customer().may_receive("I-131")
    assert a_customer(kind=CustomerKind.RESEARCH).may_receive("Lu-177")
    assert not a_customer(kind=CustomerKind.CLINIC).may_receive("I-131")
    assert a_customer(kind=CustomerKind.CLINIC).may_receive("Tc-99m")


def test_nobody_receives_the_generator_parent() -> None:
    assert not a_customer().may_receive("Mo-99")


def test_an_unknown_nuclide_is_refused_at_the_customer() -> None:
    with pytest.raises(ValidationError, match="does not handle"):
        a_customer().may_receive("Pu-239")


def test_an_authorized_user_belongs_to_a_customer() -> None:
    user = a_user()
    assert user.customer_id == "CU-0001"
    with pytest.raises(ValidationError, match="wrong kind of number"):
        a_user(customer_id="AU-0001")


def test_an_authorized_user_is_named_for_particular_nuclides() -> None:
    user = a_user()
    assert user.may_order("tc99m")
    assert user.may_order("I-131")
    assert not user.may_order("Lu-177")


def test_a_user_named_for_nothing_may_order_nothing() -> None:
    assert not a_user(nuclides=frozenset()).may_order("Tc-99m")


def test_a_nuclide_the_pharmacy_does_not_handle_is_refused_on_a_user() -> None:
    with pytest.raises(ValidationError, match="not one this pharmacy handles"):
        a_user(nuclides=frozenset({"Pu-239"}))


def test_a_user_who_has_left_is_not_current() -> None:
    left = a_user(ended_on=dt.date(2025, 9, 30))
    assert left.is_current_on(dt.date(2025, 9, 30))
    assert not left.is_current_on(dt.date(2025, 10, 1))
    assert not left.is_current_on(dt.date(2024, 12, 31))


def test_a_user_cannot_end_before_they_were_added() -> None:
    with pytest.raises(ValidationError, match="ended before"):
        a_user(ended_on=dt.date(2024, 1, 1))


def test_a_user_can_be_renamed_onto_a_different_set() -> None:
    widened = a_user().with_nuclides(["Tc-99m", "I-131", "Lu-177"])
    assert widened.may_order("Lu-177")
    assert widened.id == "AU-0004"


def test_a_customer_with_a_number_can_be_telephoned() -> None:
    reachable = a_customer(telephone="580 555 0148", department="nuclear medicine")
    assert reachable.can_be_telephoned
    assert reachable.contact() == (
        "Saint Brannon Medical Centre (nuclear medicine) on 580 555 0148"
    )


def test_a_customer_with_no_number_says_so_on_the_recall_list() -> None:
    assert not a_customer().can_be_telephoned
    assert a_customer().contact().endswith("no telephone on file")
