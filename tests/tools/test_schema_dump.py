from pathlib import Path

from molycow.store.migrations import latest
from molycow.tools import schema_dump


def test_the_document_in_the_tree_matches_the_migrations() -> None:
    assert schema_dump.main(["--check"]) == 0


def test_the_document_names_every_table() -> None:
    text = schema_dump.text()
    for table in ("customer", "elution", "batch", "dose", "shipment", "container"):
        assert f"## {table}" in text


def test_the_document_carries_the_schema_version() -> None:
    assert f"Schema version {latest()}" in schema_dump.text()


def test_columns_are_marked_where_they_are_keys_or_required() -> None:
    text = schema_dump.text()
    assert "`id` TEXT (primary key)" in text
    assert "`name` TEXT (not null)" in text
    assert "`customer_id` points at `customer.id`" in text


def test_the_indexes_are_listed() -> None:
    assert "- indexes: " in schema_dump.text()


def test_writing_puts_the_document_where_it_was_asked_for(tmp_path: Path) -> None:
    target = schema_dump.write(tmp_path / "under" / "schema.md")
    assert target.exists()
    assert target.read_text().startswith("# schema")


def test_a_missing_document_fails_the_check(tmp_path: Path, monkeypatch: object) -> None:
    import molycow.tools.schema_dump as module

    original = module.DOCUMENT
    module.DOCUMENT = tmp_path / "gone.md"
    try:
        assert module.main(["--check"]) == 1
    finally:
        module.DOCUMENT = original


def test_a_stale_document_fails_the_check(tmp_path: Path) -> None:
    import molycow.tools.schema_dump as module

    stale = tmp_path / "schema.md"
    stale.write_text("# schema\n\nout of date\n")
    original = module.DOCUMENT
    module.DOCUMENT = stale
    try:
        assert module.main(["--check"]) == 1
    finally:
        module.DOCUMENT = original
