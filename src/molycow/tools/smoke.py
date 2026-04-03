"""A morning driven end to end, against a book made for the purpose.

This is what runs against an installed wheel, where the test suite is not
there to be run. It does the same work the readme describes, in the same
order, and fails on the first command that does not do what the pharmacy
needs it to do.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from click.testing import CliRunner, Result

from molycow.cli.main import run

STEPS: tuple[tuple[str, ...], ...] = (
    ("book", "init"),
    (
        "customer",
        "add",
        "Saint Brannon Medical Centre",
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
    ),
    (
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
    ),
    (
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
    ),
    (
        "instrument",
        "add",
        "551-40922",
        "--kind",
        "dose calibrator",
        "--maker",
        "Vernay",
        "--model",
        "CRC-55tR",
        "--installed",
        "2023-06-12",
        "--calibrated",
        "2025-02-03",
    ),
    (
        "instrument",
        "source",
        "CS-9912",
        "--nuclide",
        "Cs-137",
        "--activity",
        "200 uCi",
        "--certified",
        "2019-07-01",
    ),
    (
        "instrument",
        "check",
        "IC-0001",
        "CS-9912",
        "--at",
        "2025-04-08 06:05",
        "--read",
        "175 uCi",
        "--by",
        "K. Ruzicka",
    ),
    (
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
    ),
    (
        "generator",
        "milk",
        "GEN-0001",
        "--at",
        "2025-04-08 06:30",
        "--volume",
        "10 mL",
        "--activity",
        "940 mCi",
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
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
    ),
    (
        "dose",
        "draw",
        "ORD-250407-01",
        "B-250408-01",
        "--at",
        "2025-04-08 07:40",
        "--assay",
        "25.65 mCi",
        "--by",
        "K. Ruzicka",
        "--calibrator",
        "IC-0001",
    ),
    (
        "ship",
        "pack",
        "CU-0001",
        "DS-250408-01",
        "--at",
        "2025-04-08 08:20",
        "--by",
        "K. Ruzicka",
        "--surface",
        "12",
        "--metre",
        "0.35",
    ),
    (
        "ship",
        "deliver",
        "SH-250408-01",
        "--at",
        "2025-04-08 09:05",
        "--to",
        "Reception",
    ),
    (
        "survey",
        "walk",
        "--at",
        "2025-04-08 17:40",
        "--by",
        "K. Ruzicka",
        "--read",
        "hot lab",
        "1.2",
        "--read",
        "dispensing bench",
        "0.8",
        "--read",
        "packaging",
        "0.3",
        "--read",
        "waste store",
        "2.1",
        "--wipe",
        "hot lab",
        "draw station",
        "340",
        "120",
    ),
    ("report", "day", "--on", "2025-04-08"),
)

EXPECTED: tuple[str, ...] = (
    "DS-250408-01",
    "SH-250408-01",
    "hot lab day sheet 2025-04-08",
)


def drive(book: Path, quiet: bool = False) -> list[Result]:
    """Run every step against a book, stopping at the first refusal."""
    runner = CliRunner()
    results: list[Result] = []
    for step in STEPS:
        result = runner.invoke(run, ["--book", str(book), *step])
        results.append(result)
        if not quiet:
            print(f"$ molycow {' '.join(step[:3])}")
            for line in result.output.splitlines()[:2]:
                print(f"  {line}")
        if result.exit_code != 0:
            print(f"smoke: {' '.join(step)} failed: {result.exception}")
            break
    return results


def main(argv: list[str] | None = None) -> int:
    """Drive a morning and say whether the pharmacy could have run it."""
    args = sys.argv[1:] if argv is None else argv
    quiet = "--quiet" in args
    with tempfile.TemporaryDirectory() as folder:
        results = drive(Path(folder) / "smoke.sqlite3", quiet)
    if len(results) != len(STEPS) or any(one.exit_code != 0 for one in results):
        return 1
    printed = "\n".join(one.output for one in results)
    for wanted in EXPECTED:
        if wanted not in printed:
            print(f"smoke: nothing printed {wanted!r}")
            return 1
    print(f"smoke: ok, {len(STEPS)} commands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
