import click

from molycow.cli.main import run
from molycow.tools import check_cli


def test_every_command_says_what_it_does() -> None:
    assert check_cli.findings() == []
    assert check_cli.main() == 0


def test_the_walk_reaches_the_leaf_commands() -> None:
    paths = [path for path, _ in check_cli.walk(run)]
    assert "generator milk" in paths
    assert "dose draw" in paths
    assert "report day" in paths
    assert "book" in paths


def test_every_command_module_is_on_the_root_group() -> None:
    carried = set(run.commands.values())
    for module in check_cli.group_modules():
        defined = check_cli.groups_defined_in(module)
        assert defined
        assert any(one in carried for one in defined)


def test_a_module_may_carry_more_than_one_group() -> None:
    names = {one.name for one in check_cli.groups_defined_in("register")}
    assert names == {"customer", "physician"}


def test_the_root_group_is_not_counted_as_a_module() -> None:
    assert "main" not in check_cli.group_modules()
    assert "session" not in check_cli.group_modules()
    assert "kit" in check_cli.group_modules()


def test_a_command_with_no_help_is_found() -> None:
    bare = click.Group("bare")
    bare.add_command(click.Command("quiet"))
    paths = dict(check_cli.walk(bare))
    assert paths["quiet"].help is None


def test_the_leaf_commands_carry_their_options() -> None:
    commands = dict(check_cli.walk(run))
    draw = commands["dose draw"]
    names = {option.name for option in draw.params}
    assert {"assay", "calibrator_id", "drawn_by"} <= names


def test_the_root_group_carries_a_worked_example() -> None:
    assert run.epilog
    assert "molycow generator milk" in run.epilog
    assert "molycow book laws" in run.epilog


def test_the_example_says_what_the_units_look_like() -> None:
    assert run.epilog is not None
    assert "'25 mCi'" in run.epilog
    assert "Times are local" in run.epilog


def test_a_root_group_with_no_example_is_a_finding() -> None:
    original = run.epilog
    run.epilog = None
    try:
        messages = [one.message for one in check_cli.findings()]
        assert "the root group has no worked example" in messages
    finally:
        run.epilog = original


def test_an_example_that_does_not_point_at_the_rules_is_a_finding() -> None:
    original = run.epilog
    run.epilog = "molycow book init"
    try:
        messages = [one.message for one in check_cli.findings()]
        assert any("point at the rules" in one for one in messages)
    finally:
        run.epilog = original
