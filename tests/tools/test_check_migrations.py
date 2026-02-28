from molycow.store.migrations import MIGRATIONS
from molycow.tools import check_migrations


def test_the_lock_matches_the_migrations_in_this_build() -> None:
    assert check_migrations.findings() == []
    assert check_migrations.main([]) == 0


def test_the_lock_holds_a_line_for_every_step() -> None:
    assert len(check_migrations.recorded()) == len(MIGRATIONS)
    assert check_migrations.LOCK.exists()


def test_a_line_carries_the_number_the_hash_and_the_name() -> None:
    line = check_migrations.line_for(MIGRATIONS[0])
    number, digest, name = line.split("  ")
    assert number == "001"
    assert len(digest) == 16
    assert name == MIGRATIONS[0].name


def test_the_hash_ignores_trailing_whitespace() -> None:
    from molycow.store.migrations import Migration

    plain = Migration(99, "test", "CREATE TABLE thing (id TEXT);")
    padded = Migration(99, "test", "CREATE TABLE thing (id TEXT);   \n")
    assert check_migrations.digest(plain) == check_migrations.digest(padded)


def test_a_changed_statement_changes_the_hash() -> None:
    from molycow.store.migrations import Migration

    first = Migration(99, "test", "CREATE TABLE thing (id TEXT);")
    second = Migration(99, "test", "CREATE TABLE thing (id INTEGER);")
    assert check_migrations.digest(first) != check_migrations.digest(second)


def test_the_write_mode_says_how_many_steps_it_wrote(capsys: object) -> None:
    assert check_migrations.main(["--write"]) == 0
    assert check_migrations.findings() == []
