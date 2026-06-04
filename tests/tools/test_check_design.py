from pathlib import Path

from molycow.tools import check_design


def test_the_design_note_describes_the_package_that_is_here() -> None:
    assert check_design.findings() == []
    assert check_design.main() == 0


def test_every_layer_has_a_section() -> None:
    sections = check_design.headings()
    for layer in check_design.layers():
        assert layer in sections
    assert "core" in sections


def test_every_service_is_named_in_the_note() -> None:
    text = check_design.DOCUMENT.read_text()
    for service in check_design.services():
        assert service in text
    assert "dispense" in check_design.services()


def test_a_note_that_is_not_there_is_a_finding(tmp_path: Path) -> None:
    original = check_design.DOCUMENT
    check_design.DOCUMENT = tmp_path / "design.md"
    try:
        assert check_design.findings()[0].message == "there is no design note"
    finally:
        check_design.DOCUMENT = original


def test_a_note_missing_a_layer_is_a_finding(tmp_path: Path) -> None:
    original = check_design.DOCUMENT
    thin = tmp_path / "design.md"
    thin.write_text("# design\n\n## core\n\nsomething\n")
    check_design.DOCUMENT = thin
    try:
        messages = [one.message for one in check_design.findings()]
        assert any("no section for service" in one for one in messages)
    finally:
        check_design.DOCUMENT = original
