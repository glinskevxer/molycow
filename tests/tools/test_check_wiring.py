from molycow.tools import check_wiring
from molycow.tools.walk import module_name, package_files


def test_everything_shipped_is_reachable() -> None:
    assert check_wiring.findings() == []
    assert check_wiring.main() == 0


def test_the_graph_holds_every_shipped_module() -> None:
    edges = check_wiring.graph()
    for path in package_files():
        assert module_name(path) in edges


def test_the_command_line_reaches_the_services() -> None:
    live = check_wiring.reachable()
    assert "molycow.service.dispense" in live
    assert "molycow.service.waste" in live
    assert "molycow.report.daysheet" in live


def test_the_entry_points_are_the_cli_and_the_checks() -> None:
    assert "molycow.cli.main" in check_wiring.ENTRY_POINTS
    live = check_wiring.reachable()
    assert "molycow.tools.check_layers" in live


def test_a_module_reached_only_through_a_package_still_counts() -> None:
    live = check_wiring.reachable()
    assert "molycow.model.register" in live
    assert "molycow.store.book" in live


def test_the_physics_is_reached_from_the_top() -> None:
    live = check_wiring.reachable()
    for name in ("molycow.decay", "molycow.ingrowth", "molycow.units", "molycow.nuclides"):
        assert name in live
