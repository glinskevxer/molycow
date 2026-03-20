import json
from pathlib import Path

from molycow.tools import coverage_gate

REPORT = {
    "totals": {"percent_covered": 96.4},
    "files": {
        "src/molycow/decay.py": {"summary": {"percent_covered": 100.0, "missing_lines": 0}},
        "src/molycow/units.py": {"summary": {"percent_covered": 82.5, "missing_lines": 14}},
        "src/molycow/clock.py": {"summary": {"percent_covered": 61.0, "missing_lines": 40}},
    },
}


def a_report(tmp_path: Path) -> Path:
    target = tmp_path / "coverage.json"
    target.write_text(json.dumps(REPORT))
    return target


def test_the_report_is_read_into_a_total_and_files(tmp_path: Path) -> None:
    total, files = coverage_gate.read(a_report(tmp_path))
    assert total == 96.4
    assert [one.name for one in files] == [
        "src/molycow/clock.py",
        "src/molycow/decay.py",
        "src/molycow/units.py",
    ]


def test_a_file_line_carries_the_percentage_and_what_is_missing(tmp_path: Path) -> None:
    _, files = coverage_gate.read(a_report(tmp_path))
    worst = min(files, key=lambda one: one.percent)
    assert worst.line().strip().startswith("61.00%")
    assert "40 missing" in worst.line()
    assert worst.name.endswith("clock.py")


def test_the_files_under_a_floor_come_back_worst_first(tmp_path: Path) -> None:
    _, files = coverage_gate.read(a_report(tmp_path))
    short = coverage_gate.below(files, 90.0)
    assert [one.name for one in short] == ["src/molycow/clock.py", "src/molycow/units.py"]
    assert coverage_gate.below(files, 50.0) == []


def test_a_missing_report_is_an_error(monkeypatch: object, tmp_path: Path) -> None:
    original = coverage_gate.REPORT
    coverage_gate.REPORT = tmp_path / "nothing.json"
    try:
        assert coverage_gate.main([]) == 1
    finally:
        coverage_gate.REPORT = original


def test_the_gate_holds_both_floors(tmp_path: Path) -> None:
    original = coverage_gate.REPORT
    coverage_gate.REPORT = a_report(tmp_path)
    try:
        assert coverage_gate.main(["--floor", "99", "--file-floor", "50"]) == 1
        assert coverage_gate.main(["--floor", "90", "--file-floor", "80"]) == 1
        assert coverage_gate.main(["--floor", "90", "--file-floor", "60"]) == 0
    finally:
        coverage_gate.REPORT = original


def test_a_flag_with_no_value_falls_back(tmp_path: Path) -> None:
    original = coverage_gate.REPORT
    coverage_gate.REPORT = a_report(tmp_path)
    try:
        assert coverage_gate.main(["--floor"]) == 1
    finally:
        coverage_gate.REPORT = original
