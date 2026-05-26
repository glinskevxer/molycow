import ast

from molycow.tools import check_naming


def test_every_test_in_this_suite_reads_as_a_sentence() -> None:
    assert check_naming.findings() == []
    assert check_naming.main() == 0


def test_the_names_are_read_out_of_a_module_with_their_lines() -> None:
    tree = ast.parse("def test_a_thing_is_true() -> None:\n    pass\n\ndef helper():\n    pass\n")
    assert check_naming.test_names(tree) == [("test_a_thing_is_true", 1)]


def test_a_numbered_name_is_caught_by_the_pattern() -> None:
    assert check_naming.NUMBERED.search("test_dose_2")
    assert not check_naming.NUMBERED.search("test_a_dose_is_drawn")


def test_a_short_name_is_not_a_sentence() -> None:
    assert len("test_dose_drawn".removeprefix("test_").split("_")) < check_naming.SHORTEST


def test_the_shortest_sentence_is_four_words() -> None:
    assert check_naming.SHORTEST == 4
