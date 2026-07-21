from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from molycow.cli.main import run


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def call(runner: CliRunner, bookfile: Path, *args: str) -> Result:
    return runner.invoke(run, ["--book", str(bookfile), *args])


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    target = tmp_path / "day.sqlite3"
    call(runner, target, "book", "init")
    call(
        runner,
        target,
        "customer",
        "add",
        "Saint Brannon",
        "--kind",
        "hospital",
        "--licence",
        "42-28931-01",
        "--street",
        "1400 Weir Street",
        "--town",
        "Ardmore",
        "--zone",
        "north",
        "--opened",
        "2025-01-06",
    )
    call(
        runner,
        target,
        "physician",
        "add",
        "CU-0001",
        "R. Okonkwo",
        "--licence",
        "42-28931-01",
        "--nuclide",
        "Tc-99m",
        "--added",
        "2025-01-06",
    )
    call(
        runner,
        target,
        "order",
        "take",
        "CU-0001",
        "AU-0001",
        "--code",
        "MDP",
        "--procedure",
        "whole body bone",
        "--ref",
        "A-4471902",
        "--activity",
        "22 mCi",
        "--calibration",
        "2025-04-08 09:00",
        "--at",
        "2025-04-07 16:10",
    )
    call(
        runner,
        target,
        "generator",
        "receive",
        "M99-44182",
        "--maker",
        "Corren Isotopes",
        "--activity",
        "2 Ci",
        "--calibrated",
        "2025-04-05 12:00",
        "--received",
        "2025-04-05",
        "--expires",
        "2025-04-19",
    )
    call(
        runner,
        target,
        "generator",
        "milk",
        "GEN-0001",
        "--at",
        "2025-04-08 06:30",
        "--volume",
        "10 mL",
        "--activity",
        "940 mCi",
    )
    call(
        runner,
        target,
        "generator",
        "test",
        "EL-250408-01",
        "--at",
        "2025-04-08 06:45",
        "--moly",
        "0.9 uCi",
        "--aluminium",
        "4",
        "--by",
        "K. Ruzicka",
    )
    call(
        runner,
        target,
        "kit",
        "add",
        "MDP",
        "9F4471",
        "--maker",
        "Sedgwick",
        "--received",
        "2025-03-20",
        "--expires",
        "2026-03-31",
        "--vials",
        "30",
    )
    call(
        runner,
        target,
        "kit",
        "compound",
        "MDP",
        "EL-250408-01",
        "--at",
        "2025-04-08 07:15",
        "--activity",
        "300 mCi",
        "--by",
        "K. Ruzicka",
    )
    call(
        runner,
        target,
        "kit",
        "strips",
        "B-250408-01",
        "--at",
        "2025-04-08 07:35",
        "--solvent",
        "48200",
        "1100",
        "--saline",
        "900",
        "47600",
        "--by",
        "K. Ruzicka",
    )
    return target


def a_calibrator(runner: CliRunner, bookfile: Path) -> None:
    import datetime as dt

    from tests.conftest import at

    from molycow.model.instrument import CheckSource, Instrument, InstrumentKind
    from molycow.model.qc import CheckKind, QcCheck
    from molycow.store import Book
    from molycow.store.instruments import (
        CheckSourceRepository,
        InstrumentRepository,
        QcRepository,
    )
    from molycow.units import Activity

    with Book.open(bookfile) as book:
        InstrumentRepository(book).add(
            Instrument(
                id="IC-0003",
                kind=InstrumentKind.DOSE_CALIBRATOR,
                maker="Vernay",
                model="CRC-55tR",
                serial="551-40922",
                installed_on=dt.date(2023, 6, 12),
                calibrated_on=dt.date(2025, 2, 3),
            )
        )
        CheckSourceRepository(book).add(
            CheckSource(
                serial="CS-9912",
                symbol="Cs-137",
                certified_activity=Activity.of(200, "uci"),
                certified_on=dt.date(2019, 7, 1),
            )
        )
        source = CheckSourceRepository(book).get("CS-9912")
        QcRepository(book).add(
            QcCheck(
                instrument_id="IC-0003",
                kind=CheckKind.CONSTANCY,
                at=at("2025-04-08 06:05"),
                source_serial="CS-9912",
                expected=source.activity_on(dt.date(2025, 4, 8)),
                measured=source.activity_on(dt.date(2025, 4, 8)),
                checked_by="K. Ruzicka",
            )
        )


def test_the_plan_says_what_to_draw(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
        "dose",
        "plan",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
    )
    assert "draw" in result.output
    assert "22.0 mCi at" in result.output


def test_the_bench_says_which_batches_would_fill_an_order(
    runner: CliRunner, bookfile: Path
) -> None:
    found = call(runner, bookfile, "dose", "batches", "ORD-250407-01", "--at", "2025-04-08 07:40")
    assert "B-250408-01" in found.output
    late = call(runner, bookfile, "dose", "batches", "ORD-250407-01", "--at", "2025-04-08 10:00")
    assert "nothing on the bench" in late.output


def test_a_draw_needs_a_calibrator_that_passed_this_morning(
    runner: CliRunner, bookfile: Path
) -> None:
    result = call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "24 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )
    assert result.exit_code != 0


def test_drawing_prints_the_variance_and_the_label(runner: CliRunner, bookfile: Path) -> None:
    a_calibrator(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "23.09 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )
    assert result.exit_code == 0
    assert "DS-250408-01" in result.output
    assert "at calibration" in result.output
    assert "Tc-99m medronate 22.0 mCi at 0900" in result.output


def test_a_syringe_a_long_way_off_the_order_is_refused(runner: CliRunner, bookfile: Path) -> None:
    a_calibrator(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "12 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )
    assert result.exit_code != 0
    assert "assay close enough" in str(result.exception)


def test_a_tolerance_can_be_tightened_on_the_command_line(
    runner: CliRunner, bookfile: Path
) -> None:
    a_calibrator(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "24.5 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
        "--tolerance",
        "1",
    )
    assert result.exit_code != 0


def test_the_label_can_be_reprinted(runner: CliRunner, bookfile: Path) -> None:
    a_calibrator(runner, bookfile)
    call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "23.09 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )
    label = call(runner, bookfile, "dose", "label", "DS-250408-01")
    assert label.output.strip().endswith("22.0 mCi at 0900")


def test_the_days_syringes_read_back(runner: CliRunner, bookfile: Path) -> None:
    a_calibrator(runner, bookfile)
    call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "23.09 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )
    listed = call(runner, bookfile, "dose", "list", "--on", "2025-04-08")
    assert "DS-250408-01" in listed.output
    assert "A-4471902" in listed.output
    assert (
        "nothing was drawn" in call(runner, bookfile, "dose", "list", "--on", "2025-04-09").output
    )


def test_the_batch_view_shows_what_is_left(runner: CliRunner, bookfile: Path) -> None:
    a_calibrator(runner, bookfile)
    call(
        runner,
        bookfile,
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "23.09 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0003",
    )
    result = call(runner, bookfile, "dose", "batch", "B-250408-01")
    assert "DS-250408-01" in result.output
    assert "left of B-250408-01" in result.output


def test_the_batch_list_says_the_smallest_draw(runner: CliRunner, bookfile: Path) -> None:
    a_calibrator(runner, bookfile)
    result = call(runner, bookfile, "dose", "batches", "ORD-250407-01", "--at", "2025-04-08 07:40")
    assert "smallest draw" in result.output
