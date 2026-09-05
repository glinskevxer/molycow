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


def a_pyproject(tmp_path: object, body: str) -> object:
    """A pyproject the check can be pointed at."""
    from pathlib import Path

    target = Path(str(tmp_path)) / "pyproject.toml"
    target.write_text(body, encoding="utf-8")
    return target


def findings_against(tmp_path: object, body: str) -> list[str]:
    """What the check says about one made up pyproject."""
    original = check_package.PYPROJECT
    check_package.PYPROJECT = a_pyproject(tmp_path, body)  # type: ignore[assignment]
    try:
        return [one.message for one in check_package.findings()]
    finally:
        check_package.PYPROJECT = original


WHOLE = """
[project]
name = "molycow"
version = "0.2.0"
description = "Hot lab records"
dependencies = ["click==8.1.8"]

[project.scripts]
molycow = "molycow.cli.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/molycow"]
"""


def test_a_pyproject_with_everything_in_it_passes(tmp_path: object) -> None:
    assert findings_against(tmp_path, WHOLE) == []


def test_a_package_with_no_console_script_is_found(tmp_path: object) -> None:
    body = WHOLE.replace('[project.scripts]\nmolycow = "molycow.cli.main:main"\n', "")
    assert "there is no molycow console script" in findings_against(tmp_path, body)


def test_a_script_pointing_at_a_module_that_is_not_there_is_found(
    tmp_path: object,
) -> None:
    body = WHOLE.replace("molycow.cli.main:main", "molycow.cli.nowhere:main")
    messages = findings_against(tmp_path, body)
    assert any("points at a module that is not there" in one for one in messages)


def test_a_script_pointing_at_a_missing_function_is_found(tmp_path: object) -> None:
    body = WHOLE.replace("molycow.cli.main:main", "molycow.cli.main:nothing")
    messages = findings_against(tmp_path, body)
    assert any("which is not there" in one for one in messages)


def test_a_wheel_that_carries_the_wrong_thing_is_found(tmp_path: object) -> None:
    body = WHOLE.replace('packages = ["src/molycow"]', 'packages = ["src", "tests"]')
    messages = findings_against(tmp_path, body)
    assert "the wheel does not carry exactly the package" in messages
    assert check_package.packaged() == ["src/molycow"]


def test_a_package_with_no_description_is_found(tmp_path: object) -> None:
    body = WHOLE.replace('description = "Hot lab records"', 'description = "   "')
    assert "the package has no description" in findings_against(tmp_path, body)


def test_a_package_that_declares_nothing_it_needs_is_found(tmp_path: object) -> None:
    body = WHOLE.replace('dependencies = ["click==8.1.8"]', "dependencies = []")
    assert "the package does not declare what it needs" in findings_against(tmp_path, body)


def test_the_scripts_are_read_off_the_pyproject_it_is_pointed_at(
    tmp_path: object,
) -> None:
    original = check_package.PYPROJECT
    check_package.PYPROJECT = a_pyproject(tmp_path, WHOLE)  # type: ignore[assignment]
    try:
        assert check_package.scripts() == {"molycow": "molycow.cli.main:main"}
        assert check_package.settings()["project"]["version"] == "0.2.0"  # type: ignore[index]
    finally:
        check_package.PYPROJECT = original
