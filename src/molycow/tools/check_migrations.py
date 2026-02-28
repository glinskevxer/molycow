"""A migration that has shipped is never edited again.

Every step is written into ``migrations.lock`` with a hash of the statements
it ran. A book in the field has already run those statements, so editing one
leaves two pharmacies at the same schema number with different tables. Adding
a step is ordinary work; changing one that is already in the lock is not.

Run this module with ``--write`` to add the new steps to the lock.
"""

from __future__ import annotations

import hashlib
import sys

from molycow.store.migrations import MIGRATIONS, Migration
from molycow.tools.walk import Finding, repo_root, report

LOCK = repo_root() / "migrations.lock"


def digest(step: Migration) -> str:
    """The hash the lock keeps for one step."""
    body = "\n".join(line.rstrip() for line in step.statements.strip().splitlines())
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def line_for(step: Migration) -> str:
    """One line of the lock: number, hash and name."""
    return f"{step.number:03d}  {digest(step)}  {step.name}"


def expected() -> list[str]:
    """What the lock should hold for the migrations in this build."""
    return [line_for(step) for step in MIGRATIONS]


def recorded() -> list[str]:
    """What the lock holds now."""
    if not LOCK.exists():
        return []
    return [line for line in LOCK.read_text(encoding="utf-8").splitlines() if line.strip()]


def write() -> int:
    """Put the current migrations into the lock."""
    LOCK.write_text("\n".join(expected()) + "\n", encoding="utf-8")
    return len(expected())


def findings() -> list[Finding]:
    """Every step that is missing from the lock or no longer matches it."""
    found: list[Finding] = []
    have = recorded()
    want = expected()
    for number, line in enumerate(want, start=1):
        if number > len(have):
            found.append(Finding(LOCK, number, f"step {number} is not in the lock"))
            continue
        if have[number - 1] != line:
            found.append(Finding(LOCK, number, f"step {number} has changed since it shipped"))
    if len(have) > len(want):
        found.append(Finding(LOCK, len(want) + 1, "the lock holds steps this build does not"))
    return found


def main(argv: list[str] | None = None) -> int:
    """Run the check, or rewrite the lock when asked to."""
    args = sys.argv[1:] if argv is None else argv
    if "--write" in args:
        print(f"migrations.lock written with {write()} steps")
        return 0
    return report("check_migrations", findings())


if __name__ == "__main__":
    sys.exit(main())
