import ast

from molycow.tools import check_layers
from molycow.tools.walk import parse, repo_root, source_root


def test_the_layers_only_import_downwards() -> None:
    assert check_layers.findings() == []
    assert check_layers.main() == 0


def test_every_layer_in_the_package_has_a_rule() -> None:
    layers = {
        path.name
        for path in source_root().iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    for layer in layers:
        assert layer in check_layers.BELOW


def test_a_layer_may_import_itself_and_everything_under_it() -> None:
    assert check_layers.BELOW["core"] == ()
    assert "store" in check_layers.BELOW["service"]
    assert "service" not in check_layers.BELOW["store"]
    assert "cli" not in check_layers.BELOW["report"]


def test_a_dotted_name_is_placed_in_its_layer() -> None:
    assert check_layers.layer_of_module("molycow.decay") == "core"
    assert check_layers.layer_of_module("molycow.store.book") == "store"
    assert check_layers.layer_of_module("molycow.service.elution") == "service"


def test_the_imports_of_a_file_are_read_with_their_lines() -> None:
    tree = parse(source_root() / "service" / "elution.py")
    found = dict(check_layers.imported_modules(tree))
    assert "molycow.store.book" in found
    assert all(line > 0 for line in found.values())


def test_a_module_that_imports_upwards_is_found() -> None:
    tree = ast.parse("from molycow.cli.main import run\n")
    assert check_layers.imported_modules(tree) == [("molycow.cli.main", 1)]
    assert check_layers.layer_of_module("molycow.cli.main") == "cli"


def test_only_the_package_imports_are_looked_at() -> None:
    tree = ast.parse("import click\nfrom decimal import Decimal\n")
    assert check_layers.imported_modules(tree) == []


def test_the_store_does_not_reach_into_the_services() -> None:
    for path in (source_root() / "store").glob("*.py"):
        for name, _ in check_layers.imported_modules(parse(path)):
            assert not name.startswith("molycow.service")
            assert not name.startswith("molycow.cli")


def test_the_model_does_not_reach_into_the_store() -> None:
    for path in (source_root() / "model").glob("*.py"):
        for name, _ in check_layers.imported_modules(parse(path)):
            assert not name.startswith("molycow.store")


def test_the_check_reads_the_shipped_tree_not_the_cwd() -> None:
    assert source_root().is_relative_to(repo_root())
