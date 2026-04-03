from pathlib import Path

from molycow import __version__
from molycow.tools import release_check


def test_the_package_is_ready_to_be_tagged() -> None:
    assert release_check.findings() == []
    assert release_check.main() == 0


def test_the_version_is_written_in_both_places() -> None:
    assert release_check.packaged_version() == __version__


def test_the_changelog_leads_with_the_current_version() -> None:
    versions = release_check.changelog_versions()
    assert versions
    assert versions[0] == __version__


def test_the_changelog_says_what_the_release_holds() -> None:
    text = release_check.CHANGELOG.read_text()
    assert "decay in storage" in text
    assert "possession" in text


def test_the_version_pattern_reads_a_pyproject_line() -> None:
    assert release_check.VERSION.search('version = "1.2.3"\n') is not None
    assert release_check.VERSION.search('requires-python = ">=3.12"\n') is None


def test_a_version_that_does_not_match_pyproject_is_found(tmp_path: Path) -> None:
    original = release_check.PYPROJECT
    other = tmp_path / "pyproject.toml"
    other.write_text('[project]\nversion = "9.9.9"\n')
    release_check.PYPROJECT = other
    try:
        found = release_check.findings()
        assert any("pyproject says 9.9.9" in one.message for one in found)
    finally:
        release_check.PYPROJECT = original


def test_a_pyproject_with_no_version_is_found(tmp_path: Path) -> None:
    original = release_check.PYPROJECT
    other = tmp_path / "pyproject.toml"
    other.write_text('[project]\nname = "molycow"\n')
    release_check.PYPROJECT = other
    try:
        assert release_check.packaged_version() is None
        assert any("does not declare a version" in one.message for one in release_check.findings())
    finally:
        release_check.PYPROJECT = original


def test_a_changelog_that_does_not_name_the_version_is_found(tmp_path: Path) -> None:
    original = release_check.CHANGELOG
    other = tmp_path / "CHANGELOG.md"
    other.write_text("# changelog\n\n## 0.0.1\n\nsomething else\n")
    release_check.CHANGELOG = other
    try:
        found = release_check.findings()
        assert any("does not name" in one.message for one in found)
    finally:
        release_check.CHANGELOG = original


def test_a_changelog_led_by_an_older_entry_is_found(tmp_path: Path) -> None:
    original = release_check.CHANGELOG
    other = tmp_path / "CHANGELOG.md"
    other.write_text(f"# changelog\n\n## 0.0.1\n\nold\n\n## {__version__}\n\nnew\n")
    release_check.CHANGELOG = other
    try:
        found = release_check.findings()
        assert any("newest entry" in one.message for one in found)
    finally:
        release_check.CHANGELOG = original


def test_a_stale_schema_document_stops_a_release(tmp_path: Path) -> None:
    from molycow.tools import schema_dump

    original = schema_dump.DOCUMENT
    stale = tmp_path / "schema.md"
    stale.write_text("# schema\n")
    schema_dump.DOCUMENT = stale
    try:
        assert any("schema document" in one.message for one in release_check.findings())
    finally:
        schema_dump.DOCUMENT = original


def test_a_stale_glossary_stops_a_release(tmp_path: Path) -> None:
    from molycow.tools import build_glossary

    original = build_glossary.DOCUMENT
    stale = tmp_path / "glossary.md"
    stale.write_text("# glossary\n")
    build_glossary.DOCUMENT = stale
    try:
        assert any("glossary" in one.message for one in release_check.findings())
    finally:
        build_glossary.DOCUMENT = original
