from molycow import __version__
from molycow.tools import check_package


def test_the_installable_package_is_right() -> None:
    assert check_package.findings() == []
    assert check_package.main() == 0


def test_the_package_ships_a_typed_marker() -> None:
    assert check_package.MARKER.exists()
    assert check_package.MARKER.name == "py.typed"


def test_the_console_script_points_at_something_real() -> None:
    scripts = check_package.scripts()
    assert scripts["molycow"] == "molycow.cli.main:main"


def test_the_wheel_carries_the_package_and_not_the_suite() -> None:
    assert check_package.packaged() == ["src/molycow"]


def test_the_version_is_the_one_the_package_reports() -> None:
    project = check_package.settings()["project"]
    assert isinstance(project, dict)
    assert project["version"] == __version__


def test_a_missing_marker_is_a_finding(tmp_path: object) -> None:
    from pathlib import Path

    original = check_package.MARKER
    check_package.MARKER = Path(str(tmp_path)) / "py.typed"
    try:
        messages = [one.message for one in check_package.findings()]
        assert any("py.typed" in one for one in messages)
    finally:
        check_package.MARKER = original
