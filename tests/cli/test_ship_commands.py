from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from tests.cli.support import a_working_morning, call


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    return a_working_morning(runner, tmp_path)


def pack(runner: CliRunner, bookfile: Path, *dose_ids: str) -> Result:
    return call(
        runner,
        bookfile,
        "ship",
        "pack",
        "CU-0001",
        *dose_ids,
        "--at",
        "2025-04-08 08:20",
        "--by",
        "K. Ruzicka",
        "--surface",
        "12",
        "--metre",
        "0.35",
    )


def test_a_drawn_dose_is_waiting_to_be_packed(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "ship", "ready", "CU-0001", "--at", "2025-04-08 08:20")
    assert "DS-250408-01" in result.output


def test_packing_prints_the_manifest_line(runner: CliRunner, bookfile: Path) -> None:
    result = pack(runner, bookfile, "DS-250408-01")
    assert "SH-250408-01 CU-0001 Yellow-II TI 0.4" in result.output
    assert "a2 fraction" in result.output


def test_a_packed_dose_is_no_longer_waiting(runner: CliRunner, bookfile: Path) -> None:
    pack(runner, bookfile, "DS-250408-01")
    result = call(runner, bookfile, "ship", "ready", "CU-0001", "--at", "2025-04-08 08:30")
    assert "nothing waiting" in result.output


def test_a_box_over_the_surface_limit_is_refused(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "ship",
        "pack",
        "CU-0001",
        "DS-250408-01",
        "--at",
        "2025-04-08 08:20",
        "--by",
        "K. Ruzicka",
        "--surface",
        "400",
        "--metre",
        "0.35",
    )
    assert result.exit_code != 0
    assert "surface limit" in str(result.exception)


def test_a_box_is_signed_for(runner: CliRunner, bookfile: Path) -> None:
    pack(runner, bookfile, "DS-250408-01")
    result = call(
        runner,
        bookfile,
        "ship",
        "deliver",
        "SH-250408-01",
        "--at",
        "2025-04-08 09:05",
        "--to",
        "Reception",
    )
    assert "signed by Reception" in result.output


def test_the_manifest_adds_the_index_up(runner: CliRunner, bookfile: Path) -> None:
    pack(runner, bookfile, "DS-250408-01")
    result = call(runner, bookfile, "ship", "manifest", "--on", "2025-04-08")
    assert "vehicle index 0.4" in result.output
    assert "1 doses" in result.output


def test_an_empty_dock_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert (
        "nothing left the dock"
        in call(runner, bookfile, "ship", "manifest", "--on", "2025-04-09").output
    )


def test_the_outstanding_list_empties_when_a_box_is_signed(
    runner: CliRunner, bookfile: Path
) -> None:
    pack(runner, bookfile, "DS-250408-01")
    assert "SH-250408-01" in call(runner, bookfile, "ship", "outstanding").output
    call(
        runner,
        bookfile,
        "ship",
        "deliver",
        "SH-250408-01",
        "--at",
        "2025-04-08 09:05",
        "--to",
        "Reception",
    )
    assert "everything has been signed for" in call(runner, bookfile, "ship", "outstanding").output


def test_a_box_can_be_looked_into(runner: CliRunner, bookfile: Path) -> None:
    pack(runner, bookfile, "DS-250408-01")
    call(
        runner,
        bookfile,
        "ship",
        "deliver",
        "SH-250408-01",
        "--at",
        "2025-04-08 09:05",
        "--to",
        "Reception",
    )
    result = call(runner, bookfile, "ship", "show", "SH-250408-01")
    assert "DS-250408-01" in result.output
    assert "signed by Reception" in result.output
