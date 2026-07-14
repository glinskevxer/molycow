from pathlib import Path

from molycow.rules import rules, subjects
from molycow.tools import build_rules


def test_the_document_in_the_tree_is_up_to_date() -> None:
    assert build_rules.main(["--check"]) == 0


def test_every_rule_appears_under_its_own_group() -> None:
    text = build_rules.text()
    for subject in subjects():
        assert f"## {subject}" in text
    for rule in rules():
        assert f"**{rule.code}**" in text
        assert rule.says in text


def test_the_document_counts_what_it_holds() -> None:
    assert f"{len(rules())} rules in {len(subjects())} groups" in build_rules.text()


def test_a_stale_document_fails_the_check(tmp_path: Path) -> None:
    original = build_rules.DOCUMENT
    stale = tmp_path / "rules.md"
    stale.write_text("# rules\n")
    build_rules.DOCUMENT = stale
    try:
        assert build_rules.main(["--check"]) == 1
        stale.unlink()
        assert build_rules.main(["--check"]) == 1
    finally:
        build_rules.DOCUMENT = original


def test_writing_puts_the_document_where_it_was_asked_for(tmp_path: Path) -> None:
    target = build_rules.write(tmp_path / "rules.md")
    assert target.read_text().startswith("# rules")
