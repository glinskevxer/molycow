import ast

from molycow.tools import check_sql
from molycow.tools.walk import parse, source_root


def test_no_sql_is_written_outside_the_store() -> None:
    assert check_sql.findings() == []
    assert check_sql.main() == 0


def test_the_statement_pattern_finds_the_verbs_that_matter() -> None:
    for text in (
        "SELECT * FROM dose",
        "insert into dose values (?)",
        "UPDATE customer SET closed_on = ?",
        "DELETE FROM waste_item",
        "CREATE TABLE thing (id TEXT)",
        "ALTER TABLE batch ADD COLUMN saline TEXT",
    ):
        assert check_sql.STATEMENT.search(text) is not None


def test_ordinary_prose_is_not_mistaken_for_sql() -> None:
    for text in (
        "the update went out on friday",
        "select the strongest vial",
        "update the sheet before it goes in the folder",
        "a table of half lives",
    ):
        assert check_sql.STATEMENT.search(text) is None


def test_strings_are_read_with_their_lines() -> None:
    tree = ast.parse('x = "one"\ny = "two"\n')
    assert check_sql.strings_in(tree) == [("one", 1), ("two", 2)]


def test_the_store_is_where_sql_is_allowed() -> None:
    assert "store" in check_sql.ALLOWED_LAYERS
    statements = 0
    for path in (source_root() / "store").glob("*.py"):
        for text, _ in check_sql.strings_in(parse(path)):
            if check_sql.STATEMENT.search(text):
                statements += 1
    assert statements > 20


def test_the_checks_that_read_sql_are_allowed_to_hold_it() -> None:
    assert "tools/check_sql.py" in check_sql.ALLOWED_FILES
