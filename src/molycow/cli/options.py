"""The options that mean the same thing on every command.

``--at`` is a local moment and ``--on`` is a local day, everywhere, and they
were declared fifty one times before this file existed. Declaring them once
also means the help text says the same thing in every command, which is the
part users notice.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import click

Command = TypeVar("Command", bound=Callable[..., Any])

MOMENT_HELP = "a local moment, written as '2025-04-08 07:40'"
DAY_HELP = "a local day, written as '2025-04-08'"


def at_option(help_text: str = MOMENT_HELP) -> Callable[[Command], Command]:
    """The moment something happened, which every bench command needs."""
    return click.option("--at", "moment", required=True, help=help_text)


def at_option_maybe(help_text: str = MOMENT_HELP) -> Callable[[Command], Command]:
    """The same moment, on a command that has a sensible answer without one."""
    return click.option("--at", "moment", default=None, help=help_text)


def on_option(help_text: str = DAY_HELP) -> Callable[[Command], Command]:
    """The day a command works over."""
    return click.option("--on", "on_day", required=True, help=help_text)


def on_option_maybe(help_text: str = DAY_HELP) -> Callable[[Command], Command]:
    """The day a command works over, when it will take the whole book without one."""
    return click.option("--on", "on_day", default=None, help=help_text)
