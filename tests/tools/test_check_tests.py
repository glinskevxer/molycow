from molycow.tools import check_tests
from molycow.tools.walk import module_name, package_files


def test_every_shipped_module_is_named_by_a_test() -> None:
    assert check_tests.findings() == []
    assert check_tests.main() == 0


def test_an_alias_import_counts_as_importing_the_module() -> None:
    seen = check_tests.imported_by_tests()
    assert "molycow.tools.check_layers" in seen
    assert "molycow.store.book" in seen


def test_a_command_group_is_covered_by_the_file_that_drives_it() -> None:
    assert check_tests.driven_through_the_cli("molycow.cli.kit")
    assert not check_tests.driven_through_the_cli("molycow.cli.nowhere")
    assert not check_tests.driven_through_the_cli("molycow.store.book")


def test_the_package_root_is_the_only_thing_exempt() -> None:
    assert frozenset({"molycow"}) == check_tests.EXEMPT
    names = {module_name(path) for path in package_files()}
    assert "molycow" in names
