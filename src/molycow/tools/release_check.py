"""What has to be true before this package is tagged.

The version is written in two places and they have to agree. The changelog has
to name it. The migration lock and the generated documents have to be current,
because a release that ships a stale schema document is a release that lies
about its own tables.
"""

from __future__ import annotations

import re
import sys

from molycow import __version__
from molycow.tools import build_glossary, check_migrations, schema_dump
from molycow.tools.walk import Finding, repo_root, report

PYPROJECT = repo_root() / "pyproject.toml"
CHANGELOG = repo_root() / "CHANGELOG.md"

VERSION = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)


def packaged_version() -> str | None:
    """The version pyproject declares."""
    match = VERSION.search(PYPROJECT.read_text(encoding="utf-8"))
    return None if match is None else match.group(1)


def changelog_versions() -> list[str]:
    """Every version the changelog has a heading for, newest first."""
    return re.findall(r"^## (\S+)$", CHANGELOG.read_text(encoding="utf-8"), re.MULTILINE)


def findings() -> list[Finding]:
    """Everything that would make this a release nobody should tag."""
    found: list[Finding] = []
    declared = packaged_version()
    if declared is None:
        found.append(Finding(PYPROJECT, 1, "pyproject does not declare a version"))
    elif declared != __version__:
        found.append(
            Finding(
                PYPROJECT,
                1,
                f"pyproject says {declared} and the package says {__version__}",
            )
        )
    versions = changelog_versions()
    if __version__ not in versions:
        found.append(Finding(CHANGELOG, 1, f"the changelog does not name {__version__}"))
    elif versions[0] != __version__:
        found.append(Finding(CHANGELOG, 1, f"the changelog's newest entry is not {__version__}"))
    found.extend(check_migrations.findings())
    if schema_dump.main(["--check"]) != 0:
        found.append(Finding(schema_dump.DOCUMENT, 1, "the schema document is out of date"))
    if build_glossary.main(["--check"]) != 0:
        found.append(Finding(build_glossary.DOCUMENT, 1, "the glossary is out of date"))
    return found


def main() -> int:
    """Run the check and give back the status ci should see."""
    return report("release_check", findings())


if __name__ == "__main__":
    sys.exit(main())
