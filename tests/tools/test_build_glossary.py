from pathlib import Path

from molycow.formulary import codes
from molycow.glossary import TERMS, find, terms
from molycow.tools import build_glossary


def test_the_document_in_the_tree_is_up_to_date() -> None:
    assert build_glossary.main(["--check"]) == 0


def test_the_terms_are_listed_in_order() -> None:
    words = [one.word for one in terms()]
    assert words == sorted(words)
    assert len(words) == len(TERMS)


def test_a_term_is_found_by_its_word() -> None:
    found = find("Breakthrough")
    assert found is not None
    assert "molybdenum" in found.meaning.lower()
    assert find("gossip") is None


def test_a_term_with_another_name_says_so() -> None:
    line = find("generator")
    assert line is not None
    assert line.line().endswith("Also called a cow.")


def test_a_term_without_another_name_stops_at_the_meaning() -> None:
    line = find("unit dose")
    assert line is not None
    assert not line.line().endswith("Also called .")


def test_the_nuclide_table_is_generated_into_the_document() -> None:
    text = build_glossary.text()
    assert "| Tc-99m | 6.0067 | diagnostic |" in text
    assert "| I-131 | 192.605 | therapeutic |" in text


def test_every_kit_appears_in_the_document() -> None:
    text = build_glossary.text()
    for code in codes():
        assert f"| {code} |" in text


def test_a_stale_document_fails_the_check(tmp_path: Path) -> None:
    import molycow.tools.build_glossary as module

    stale = tmp_path / "glossary.md"
    stale.write_text("# glossary\n")
    original = module.DOCUMENT
    module.DOCUMENT = stale
    try:
        assert module.main(["--check"]) == 1
        stale.unlink()
        assert module.main(["--check"]) == 1
    finally:
        module.DOCUMENT = original


def test_writing_puts_the_document_where_it_was_asked_for(tmp_path: Path) -> None:
    target = build_glossary.write(tmp_path / "glossary.md")
    assert target.read_text().startswith("# glossary")
