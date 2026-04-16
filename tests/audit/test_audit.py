import datetime as dt

import pytest
from tests.conftest import at

from molycow.clock import zone
from molycow.errors import ValidationError
from molycow.model.audit import ACTIONS, Entry
from molycow.store import Book
from molycow.store.audit import AuditRepository

WHEN = at("2025-04-08 06:30")


def an_entry(**changed: object) -> Entry:
    fields: dict[str, object] = {
        "at": WHEN,
        "actor": "K. Ruzicka",
        "action": "milked",
        "subject": "EL-250408-01",
        "detail": "940.0 mCi in 10.000 mL",
    }
    fields.update(changed)
    return Entry(**fields)  # type: ignore[arg-type]


def test_an_entry_says_who_did_what_to_which_record() -> None:
    entry = an_entry()
    assert entry.actor == "K. Ruzicka"
    assert entry.subject == "EL-250408-01"
    assert "milked" in entry.line()


def test_the_line_prints_in_the_zone_it_is_given() -> None:
    line = an_entry().line(zone("UTC"))
    assert "2025-04-08 11:30 UTC" in line


def test_an_entry_without_a_detail_stops_at_the_subject() -> None:
    assert an_entry(detail="").line().rstrip().endswith("EL-250408-01")


def test_an_entry_needs_somebody_to_have_done_it() -> None:
    with pytest.raises(ValidationError, match="says who did it"):
        an_entry(actor="  ")


def test_only_the_actions_the_trail_knows_are_recorded() -> None:
    with pytest.raises(ValidationError, match="not one of the actions"):
        an_entry(action="fiddled")
    for action in ACTIONS:
        assert an_entry(action=action).action == action


def test_the_subject_has_to_be_a_label_number() -> None:
    with pytest.raises(ValidationError, match="not a label number"):
        an_entry(subject="the red one")
    assert an_entry(subject=" el-250408-01 ").subject == "EL-250408-01"


def test_the_trail_comes_back_in_the_order_it_happened(book: Book) -> None:
    repo = AuditRepository(book)
    repo.record(at("2025-04-08 07:15"), "K. Ruzicka", "compounded", "B-250408-01")
    repo.record(WHEN, "K. Ruzicka", "milked", "EL-250408-01")
    assert [one.subject for one in repo.all()] == ["EL-250408-01", "B-250408-01"]
    assert repo.count() == 2


def test_the_trail_is_read_by_subject_and_by_person(book: Book) -> None:
    repo = AuditRepository(book)
    repo.record(WHEN, "K. Ruzicka", "milked", "EL-250408-01")
    repo.record(at("2025-04-08 07:15"), "P. Vantrease", "compounded", "B-250408-01")
    assert len(repo.for_subject("EL-250408-01")) == 1
    assert len(repo.by_actor("P. Vantrease")) == 1
    assert repo.for_subject("EL-250408-09") == []


def test_the_trail_is_read_by_day(book: Book) -> None:
    repo = AuditRepository(book)
    repo.record(WHEN, "K. Ruzicka", "milked", "EL-250408-01")
    repo.record(at("2025-04-09 06:30"), "K. Ruzicka", "milked", "EL-250409-01")
    assert len(repo.on_day(dt.date(2025, 4, 8))) == 1
    assert repo.on_day(dt.date(2025, 4, 10)) == []


def test_an_entry_survives_the_round_trip(book: Book) -> None:
    repo = AuditRepository(book)
    repo.add(an_entry())
    back = repo.all()[0]
    assert back == an_entry()


def test_a_morning_leaves_a_trail_behind_it(book: Book) -> None:
    from decimal import Decimal

    from tests.support import a_working_day

    from molycow.service.dispense import DispenseService
    from molycow.service.shipping import ShippingService

    day = a_working_day(book)
    dispensing = DispenseService(book)
    planned = dispensing.plan(day.order_id, day.batch_id, at("2025-04-08 07:40"))
    dose = dispensing.draw(
        day.order_id,
        day.batch_id,
        at("2025-04-08 07:40"),
        planned.needed,
        "K. Ruzicka",
        day.calibrator_id,
    )
    ShippingService(book).pack(
        "CU-0001", [dose.id], at("2025-04-08 08:20"), "K. Ruzicka", Decimal(12), Decimal("0.35")
    )
    actions = [one.action for one in AuditRepository(book).all()]
    assert actions == [
        "checked",
        "milked",
        "tested",
        "compounded",
        "released",
        "drew",
        "packed",
    ]


def test_the_trail_names_the_record_it_is_about(book: Book) -> None:
    from tests.support import an_elution

    elution_id = an_elution(book)
    trail = AuditRepository(book).for_subject(elution_id)
    assert [one.action for one in trail] == ["milked", "tested"]
    assert "940.0 mCi from GEN-0027" in trail[0].detail


def test_a_failed_test_says_so_in_the_trail(book: Book) -> None:
    from decimal import Decimal

    from tests.support import an_elution

    from molycow.service.breakthrough import BreakthroughService
    from molycow.units import Activity

    elution_id = an_elution(book, tested=False)
    BreakthroughService(book).test(
        elution_id, at("2025-04-08 06:45"), Activity.of(400, "uci"), Decimal(4), "K. Ruzicka"
    )
    trail = AuditRepository(book).for_subject(elution_id)
    assert trail[-1].detail == "molybdenum breakthrough over the limit"


def test_a_held_batch_is_recorded_as_held(book: Book) -> None:
    from decimal import Decimal

    from tests.support import a_batch

    from molycow.model.purity import Strip, System
    from molycow.service.purity import PurityService

    batch_id = a_batch(book)
    PurityService(book).run(
        batch_id,
        at("2025-04-08 07:35"),
        Strip(System.SOLVENT, origin=40000, front=9000),
        Strip(System.SALINE, origin=900, front=47600),
        "K. Ruzicka",
    )
    assert AuditRepository(book).for_subject(batch_id)[-1].action == "held"
    assert Decimal(1) > 0


def test_a_refused_step_leaves_nothing_in_the_trail(book: Book) -> None:
    from tests.support import a_generator

    from molycow.errors import RuleError
    from molycow.service.elution import ElutionService
    from molycow.units import Activity, Volume

    a_generator(book)
    with pytest.raises(RuleError):
        ElutionService(book).milk(
            "GEN-0027", at("2025-04-08 06:30"), Volume.of(10), Activity.of(100, "mci")
        )
    assert AuditRepository(book).count() == 0
