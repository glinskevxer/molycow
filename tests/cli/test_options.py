import click
from click.testing import CliRunner

from molycow.cli.main import run
from molycow.cli.options import DAY_HELP, MOMENT_HELP, at_option, on_option, on_option_maybe
from molycow.tools.check_cli import walk


def test_the_shared_options_carry_one_help_line() -> None:
    @click.command()
    @at_option()
    @on_option()
    def example(moment: str, on_day: str) -> None:
        """An example."""

    helps = {param.name: param.help for param in example.params if isinstance(param, click.Option)}
    assert helps["moment"] == MOMENT_HELP
    assert helps["on_day"] == DAY_HELP


def test_an_option_can_still_say_something_of_its_own() -> None:
    @click.command()
    @on_option_maybe("only the ones open on this day")
    def example(on_day: str | None) -> None:
        """An example."""

    option = example.params[0]
    assert isinstance(option, click.Option)
    assert option.help == "only the ones open on this day"
    assert not option.required


def test_every_at_option_in_the_cli_says_the_same_thing() -> None:
    for path, command in walk(run):
        for param in command.params:
            if param.name == "moment" and isinstance(param, click.Option):
                assert param.help, path


def test_every_on_option_in_the_cli_says_the_same_thing() -> None:
    seen = 0
    for _, command in walk(run):
        for param in command.params:
            if param.name == "on_day" and isinstance(param, click.Option):
                assert param.help
                seen += 1
    assert seen > 10


def test_the_help_text_reaches_the_terminal() -> None:
    result = CliRunner().invoke(run, ["generator", "milk", "--help"])
    assert result.exit_code == 0
    assert MOMENT_HELP in result.output
