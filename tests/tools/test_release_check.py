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
