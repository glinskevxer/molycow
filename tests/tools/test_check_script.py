import re
import stat

from molycow.tools.walk import repo_root, source_root

SCRIPT = repo_root() / "check.sh"
WORKFLOW = repo_root() / ".github" / "workflows" / "ci.yml"


def test_the_check_script_is_in_the_checkout_and_runnable() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR


def test_the_script_runs_every_check_the_package_has() -> None:
    text = SCRIPT.read_text()
    for path in (source_root() / "tools").glob("check_*.py"):
        assert path.stem in text


def test_the_workflow_runs_every_check_as_well() -> None:
    text = WORKFLOW.read_text()
    for path in (source_root() / "tools").glob("check_*.py"):
        assert f"molycow.tools.{path.stem}" in text


def test_the_script_gates_each_step_on_its_own_status() -> None:
    text = SCRIPT.read_text()
    assert "failed+=" in text
    assert "set -uo pipefail" in text
    assert " && " not in text


def test_the_workflow_runs_the_script_as_a_job() -> None:
    assert "./check.sh" in WORKFLOW.read_text()


def test_the_workflow_still_covers_the_generated_documents() -> None:
    text = WORKFLOW.read_text()
    assert "schema_dump --check" in text
    assert "build_glossary --check" in text


def test_every_job_installs_the_pins() -> None:
    text = WORKFLOW.read_text()
    installs = re.findall(r"python -m pip install (.+)", text)
    assert installs
    for line in installs:
        assert (
            "--upgrade pip" in line or "-c constraints.txt" in line or line in {".", "dist/*.whl"}
        )
