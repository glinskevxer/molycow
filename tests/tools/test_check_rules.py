from molycow.rules import BY_CODE, about, find, rules, subjects
from molycow.tools import check_rules


def test_every_refusal_in_the_tree_is_written_down() -> None:
    assert check_rules.findings() == []
    assert check_rules.main() == 0


def test_the_codes_are_read_out_of_the_refusals() -> None:
    raised = check_rules.raised_codes()
    assert "eluate-untested" in raised
    assert "possession-limit" in raised
    for code, (path, line) in raised.items():
        assert code == code.lower()
        assert line > 0
        assert path.endswith(".py")


def test_a_rule_is_found_by_its_short_name() -> None:
    found = find("Eluate-Untested")
    assert found is not None
    assert found.about == "eluate"
    assert find("gossip") is None


def test_the_rules_are_grouped_by_what_they_are_about() -> None:
    assert "routes" in subjects()
    assert "waste" in subjects()
    for rule in about("routes"):
        assert rule.about == "routes"
    assert len(about("nothing")) == 0


def test_every_rule_says_something_in_plain_words() -> None:
    for rule in rules():
        assert rule.says
        assert rule.says[0].islower()
        assert not rule.says.endswith(".")
        assert rule.code in BY_CODE


def test_a_rule_prints_as_a_line() -> None:
    found = find("van-index")
    assert found is not None
    assert found.line().startswith("van-index")
    assert "transport index" in found.line()
