import ast
from pathlib import Path

from molycow.tools import check_docstrings
from molycow.tools.walk import (
    layer_of,
    module_name,
    package_files,
    parse,
    public_definitions,
    repo_root,
    source_files,
    suite_files,
)


def test_the_repository_root_is_found_from_the_file_not_the_cwd() -> None:
    root = repo_root()
    assert (root / "pyproject.toml").exists()
    assert (root / "src" / "molycow").is_dir()


def test_the_walk_finds_the_shipped_files_and_the_suite() -> None:
    shipped = source_files()
    assert any(path.name == "decay.py" for path in shipped)
    assert not any(path.name == "__init__.py" for path in shipped)
    assert any(path.name == "__init__.py" for path in package_files())
    assert any(path.name.startswith("test_") for path in suite_files())


def test_a_module_knows_its_dotted_name_and_its_layer() -> None:
    root = repo_root() / "src" / "molycow"
    assert module_name(root / "decay.py") == "molycow.decay"
    assert module_name(root / "store" / "book.py") == "molycow.store.book"
    assert module_name(root / "store" / "__init__.py") == "molycow.store"
    assert layer_of(root / "decay.py") == "core"
    assert layer_of(root / "service" / "elution.py") == "service"


def test_every_shipped_file_has_a_docstring_on_everything_public() -> None:
    assert check_docstrings.findings() == []


def test_the_check_finds_a_module_with_no_docstring(tmp_path: Path) -> None:
    target = tmp_path / "bare.py"
    target.write_text("def open_the_drum() -> None:\n    return None\n")
    tree = parse(target)
    assert ast.get_docstring(tree) is None
    assert [node.name for node in public_definitions(tree)] == ["open_the_drum"]


def test_a_private_name_is_not_public(tmp_path: Path) -> None:
    target = tmp_path / "quiet.py"
    target.write_text('"""A module."""\n\n\ndef _helper() -> None:\n    return None\n')
    assert list(public_definitions(parse(target))) == []


def test_a_finding_prints_as_a_path_and_a_line() -> None:
    from molycow.tools.walk import Finding

    found = Finding(repo_root() / "src" / "molycow" / "decay.py", 4, "something")
    assert found.format() == "src/molycow/decay.py:4: something"


def test_the_check_passes_on_this_repository() -> None:
    assert check_docstrings.main() == 0
