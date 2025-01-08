import pytest

from molycow.errors import (
    ConflictError,
    MolycowError,
    NotFoundError,
    ReleaseError,
    RuleError,
    SafetyError,
    ValidationError,
)


def test_a_bare_message_prints_as_written() -> None:
    assert str(MolycowError("elution not found")) == "elution not found"


def test_detail_is_appended_in_a_stable_order() -> None:
    err = MolycowError("vial is short", vial="V-4", wanted="25 mCi", have="19 mCi")
    assert str(err) == "vial is short (have=19 mCi, vial=V-4, wanted=25 mCi)"


def test_detail_stays_available_as_a_mapping() -> None:
    err = ValidationError("bad unit", unit="mBq")
    assert err.detail == {"unit": "mBq"}
    assert err.message == "bad unit"


def test_a_rule_error_names_its_rule_first() -> None:
    err = RuleError("moly-breakthrough", "over the limit", ratio="0.21")
    assert str(err) == "[moly-breakthrough] over the limit (ratio=0.21)"
    assert err.rule == "moly-breakthrough"


def test_every_error_is_catchable_as_the_base() -> None:
    for err in (
        ValidationError("v"),
        NotFoundError("n"),
        ConflictError("c"),
        RuleError("r", "m"),
        ReleaseError("r", "m"),
        SafetyError("s", "m"),
    ):
        with pytest.raises(MolycowError):
            raise err


def test_the_exit_codes_are_distinct_per_class() -> None:
    codes = {
        cls.exit_code
        for cls in (
            MolycowError,
            ValidationError,
            NotFoundError,
            ConflictError,
            RuleError,
            ReleaseError,
            SafetyError,
        )
    }
    assert len(codes) == 7


def test_release_and_safety_are_rules() -> None:
    assert issubclass(ReleaseError, RuleError)
    assert issubclass(SafetyError, RuleError)
    assert str(SafetyError("wipe-limit", "wipe over limit")) == "[wipe-limit] wipe over limit"
