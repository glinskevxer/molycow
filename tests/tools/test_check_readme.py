from pathlib import Path

from molycow.store.migrations import latest
from molycow.tools import check_readme


def test_the_worked_example_still_does_what_the_readme_says() -> None:
    assert check_readme.findings() == []
    assert check_readme.main() == 0


def test_the_transcript_is_read_as_commands_and_output() -> None:
    steps = check_readme.steps()
    assert len(steps) > 8
    first = steps[0]
    assert first.command.startswith("--book day.sqlite3 book init")
    assert first.expected[0].endswith(f"is at schema {latest()}, {latest()} steps applied")


def test_a_continued_command_line_is_joined_up() -> None:
    joined = [one for one in check_readme.steps() if "customer add" in one.command]
    assert joined
    assert "--zone north" in joined[0].command
    assert "\\" not in joined[0].command


def test_every_step_has_a_line_number_in_the_readme() -> None:
    numbers = [one.line for one in check_readme.steps()]
    assert numbers == sorted(numbers)
    assert all(number > 0 for number in numbers)


def test_the_readme_quotes_the_schema_this_build_makes() -> None:
    assert f"schema {latest()}" in check_readme.README.read_text()


def test_replaying_a_step_gives_back_what_it_printed(tmp_path: Path) -> None:
    book = tmp_path / "day.sqlite3"
    first = check_readme.steps()[0]
    printed = check_readme.replay(first, book)
    assert printed[0].startswith("day.sqlite3 is at schema")
    assert book.exists()


def test_a_step_that_fails_reads_as_an_error(tmp_path: Path) -> None:
    step = check_readme.Step(1, "--book day.sqlite3 book counts", ())
    printed = check_readme.replay(step, tmp_path / "nothing.sqlite3")
    assert printed[0].startswith("error: there is no book")


def test_the_update_mode_leaves_a_correct_readme_alone() -> None:
    before = check_readme.README.read_text()
    assert check_readme.main(["--update"]) == 0
    assert check_readme.README.read_text() == before


def test_the_update_mode_rewrites_an_output_that_has_moved(tmp_path: Path) -> None:
    original = check_readme.README
    copy = tmp_path / "README.md"
    copy.write_text(
        original.read_text().replace(
            "day.sqlite3 is at schema", "day.sqlite3 is at schema 3 and", 1
        )
    )
    check_readme.README = copy
    try:
        assert check_readme.findings()
        assert check_readme.rewrite() >= 1
        assert check_readme.findings() == []
    finally:
        check_readme.README = original


def test_the_transcript_carries_the_whole_day_sheet() -> None:
    text = check_readme.README.read_text()
    assert "hot lab day sheet 2025-04-08" in text
    assert "on the premises at midnight" in text
