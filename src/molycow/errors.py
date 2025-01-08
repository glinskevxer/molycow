"""Every error the package raises on purpose.

A caller catches :class:`MolycowError` to catch all of them. The CLI turns the
``exit_code`` on the class into the process status, so a script driving the
pharmacy can tell a typo apart from a rule the lab is not allowed to break.
"""

from __future__ import annotations

from typing import Any


class MolycowError(Exception):
    """Base for everything this package raises deliberately."""

    exit_code = 1

    def __init__(self, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.message = message
        self.detail: dict[str, Any] = detail

    def __str__(self) -> str:
        if not self.detail:
            return self.message
        parts = ", ".join(f"{k}={self.detail[k]}" for k in sorted(self.detail))
        return f"{self.message} ({parts})"


class ValidationError(MolycowError):
    """A value is the wrong shape: a bad unit, a negative volume, a stray id."""

    exit_code = 2


class NotFoundError(MolycowError):
    """A record the caller named is not in the book."""

    exit_code = 3


class ConflictError(MolycowError):
    """A record the caller wants to create is already there."""

    exit_code = 4


class RuleError(MolycowError):
    """A rule of the lab says no.

    ``rule`` is the short name the rule goes by in the procedure manual, so a
    message can be traced back to the paragraph that produced it.
    """

    exit_code = 5

    def __init__(self, rule: str, message: str, **detail: Any) -> None:
        super().__init__(message, **detail)
        self.rule = rule

    def __str__(self) -> str:
        return f"[{self.rule}] {super().__str__()}"


class ReleaseError(RuleError):
    """A dose or a batch cannot be released for a patient."""

    exit_code = 6


class SafetyError(RuleError):
    """A radiation safety limit stops the work: a survey, a leak, a licence."""

    exit_code = 7
