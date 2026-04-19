from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from molycow.cli.main import run


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def bookfile(tmp_path: Path, runner: CliRunner) -> Path:
    target = tmp_path / "day.sqlite3"
    runner.invoke(run, ["--book", str(target), "book", "init"])
    return target


def call(runner: CliRunner, bookfile: Path, *args: str) -> Result:
    return runner.invoke(run, ["--book", str(bookfile), *args])


def a_bench(runner: CliRunner, bookfile: Path) -> None:
    call(
        runner,
        bookfile,
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
        bookfile,
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
        bookfile,
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
        bookfile,
        "kit",
        "add",
        "MDP",
        "9F4471",
        "--maker",
        "Sedgwick Radiochem",
        "--received",
        "2025-03-20",
        "--expires",
        "2026-03-31",
        "--vials",
        "30",
    )


def test_the_formulary_prints_the_monographs(runner: CliRunner, bookfile: Path) -> None:
    result = call(runner, bookfile, "kit", "formulary")
    assert "MDP" in result.output
    assert "medronate" in result.output
    assert "rcp 90%" in result.output


def test_a_kit_lot_goes_on_the_shelf(runner: CliRunner, bookfile: Path) -> None:
    result = call(
        runner,
        bookfile,
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
    assert result.output.startswith("KL-0001 MDP lot 9F4471 30 vials")
    assert "KL-0001" in call(runner, bookfile, "kit", "shelf").output


def test_an_empty_shelf_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert "nothing on the shelf" in call(runner, bookfile, "kit", "shelf").output


def test_the_shelf_can_be_narrowed(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    assert "KL-0001" in call(runner, bookfile, "kit", "shelf", "--code", "MDP").output
    assert "nothing" in call(runner, bookfile, "kit", "shelf", "--code", "MAA").output
    assert "nothing" in call(runner, bookfile, "kit", "shelf", "--on", "2026-06-01").output


def test_a_prep_is_planned_before_it_is_made(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "kit",
        "plan",
        "MDP",
        "EL-250408-01",
        "--at",
        "2025-04-08 07:15",
        "--activity",
        "300 mCi",
    )
    assert "draw" in result.output
    assert "saline" in result.output
    assert "KL-0001" in result.output


def test_compounding_writes_the_batch(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    result = call(
        runner,
        bookfile,
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
    assert "B-250408-01 MDP 300.0 mCi" in result.output
    assert "expires" in result.output


def test_a_prep_outside_the_insert_is_refused(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "kit",
        "compound",
        "MDP",
        "EL-250408-01",
        "--at",
        "2025-04-08 07:15",
        "--activity",
        "800 mCi",
        "--by",
        "K. Ruzicka",
    )
    assert result.exit_code != 0
    assert "insert" in str(result.exception)


def test_the_bench_holds_a_batch_until_the_strips_are_read(
    runner: CliRunner, bookfile: Path
) -> None:
    a_bench(runner, bookfile)
    call(
        runner,
        bookfile,
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
    held = call(runner, bookfile, "kit", "bench", "--at", "2025-04-08 08:00")
    assert "held: no purity reading yet" in held.output
    strips = call(
        runner,
        bookfile,
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
    assert "95.9%" in strips.output
    ready = call(runner, bookfile, "kit", "bench", "--at", "2025-04-08 08:00")
    assert "ready" in ready.output


def test_a_dirty_batch_stays_held_and_says_which_impurity(
    runner: CliRunner, bookfile: Path
) -> None:
    a_bench(runner, bookfile)
    call(
        runner,
        bookfile,
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
    strips = call(
        runner,
        bookfile,
        "kit",
        "strips",
        "B-250408-01",
        "--at",
        "2025-04-08 07:35",
        "--solvent",
        "40000",
        "9000",
        "--saline",
        "900",
        "47600",
        "--by",
        "K. Ruzicka",
    )
    assert "held at" in strips.output
    assert "free pertechnetate" in strips.output


def test_the_days_batches_read_back(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    call(
        runner,
        bookfile,
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
    result = call(runner, bookfile, "kit", "day", "--on", "2025-04-08")
    assert "B-250408-01" in result.output
    assert "no strips" in result.output
    assert (
        "nothing was compounded"
        in call(runner, bookfile, "kit", "day", "--on", "2025-04-09").output
    )


def test_an_empty_bench_says_so(runner: CliRunner, bookfile: Path) -> None:
    assert (
        "nothing on the bench"
        in call(runner, bookfile, "kit", "bench", "--at", "2025-04-08 08:00").output
    )


def test_a_lot_is_pulled_and_the_chain_printed(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    call(
        runner,
        bookfile,
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
    result = call(
        runner,
        bookfile,
        "kit",
        "recall",
        "KL-0001",
        "--at",
        "2025-04-10 09:00",
        "--why",
        "maker found particulates",
        "--by",
        "K. Ruzicka",
    )
    assert "KL-0001 MDP lot 9F4471" in result.output
    assert "batch B-250408-01" in result.output


def test_a_lot_that_touched_nothing_says_so(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    result = call(
        runner,
        bookfile,
        "kit",
        "recall",
        "KL-0001",
        "--at",
        "2025-04-10 09:00",
        "--why",
        "maker found particulates",
        "--by",
        "K. Ruzicka",
    )
    assert "nothing was made from it" in result.output


def test_the_recalled_list_is_empty_until_something_is_pulled(
    runner: CliRunner, bookfile: Path
) -> None:
    a_bench(runner, bookfile)
    assert "nothing has been recalled" in call(runner, bookfile, "kit", "recalled").output
    call(
        runner,
        bookfile,
        "kit",
        "recall",
        "KL-0001",
        "--at",
        "2025-04-10 09:00",
        "--why",
        "maker found particulates",
        "--by",
        "K. Ruzicka",
    )
    listed = call(runner, bookfile, "kit", "recalled")
    assert "pulled 2025-04-10" in listed.output
    assert "particulates" in listed.output


def test_a_pulled_lot_cannot_be_compounded_from(runner: CliRunner, bookfile: Path) -> None:
    a_bench(runner, bookfile)
    call(
        runner,
        bookfile,
        "kit",
        "recall",
        "KL-0001",
        "--at",
        "2025-04-08 07:00",
        "--why",
        "maker found particulates",
        "--by",
        "K. Ruzicka",
    )
    result = call(
        runner,
        bookfile,
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
    assert result.exit_code != 0
    assert "no kit of that sort" in str(result.exception)
