from winget_gui.winget import WINGET_CODES
from winget_gui.ui.main_window import MainWindow
from winget_gui.workers import OperationWorker


def test_winget_code_map():
    assert WINGET_CODES[0] == "success"
    assert "no_applicable_upgrade" in WINGET_CODES.values()


def test_wildcard_exclusion(qtbot):
    window = MainWindow.__new__(MainWindow)
    window.config = {"excluded_patterns": ["*adobe*"], "excluded_ids": [], "exclude_unknown_versions": False}
    assert window._should_exclude({"Name": "Adobe Reader", "Id": "Adobe.Reader", "Version": "1"})


def test_operation_worker_emits_progress_step(qtbot):
    class Backend:
        def operation(self, args, timeout=1800, cancelled=None): return 0, ""
    worker = OperationWorker([(["upgrade"], "Example.App", "Upgrade", "Example")], Backend())
    received = []
    started = []
    worker.progress_step.connect(lambda current, total, name: received.append((current, total, name)))
    worker.package_started.connect(lambda pkg_id, label: started.append((pkg_id, label)))
    with qtbot.waitSignal(worker.finished, timeout=2000): worker.start()
    assert received == [(1, 1, "Example")]
    assert started == [("Example.App", "Upgrade")]


def test_package_model_data_and_status(qtbot):
    from PyQt6 import QtCore
    from winget_gui.ui.main_window import PackageModel
    from winget_gui.ui.theme import get_status_color

    model = PackageModel()
    model.set_rows([
        {"Name": "Test App", "Id": "Test.App", "Version": "1.0.0", "AvailableVersion": "2.0.0"},
    ])
    assert model.rowCount() == 1
    assert model.columnCount() == 6
    assert model.data(model.index(0, 1), QtCore.Qt.ItemDataRole.DisplayRole) == "Test App"
    assert model.data(model.index(0, 2), QtCore.Qt.ItemDataRole.DisplayRole) == "Test.App"
    assert model.data(model.index(0, 3), QtCore.Qt.ItemDataRole.DisplayRole) == "1.0.0"
    assert model.data(model.index(0, 4), QtCore.Qt.ItemDataRole.DisplayRole) == "2.0.0"
    assert model.data(model.index(0, 5), QtCore.Qt.ItemDataRole.DisplayRole) == "● Update available"

    # Status foreground colors
    color = model.data(model.index(0, 5), QtCore.Qt.ItemDataRole.ForegroundRole)
    assert color == get_status_color("available", "Dark")


def test_theme_stylesheets_and_colors():
    from winget_gui.ui.theme import stylesheet, get_status_color, resolve_theme_mode

    assert resolve_theme_mode("Dark") == "Dark"
    assert resolve_theme_mode("Light") == "Light"
    assert "QWidget" in stylesheet("Dark")
    assert "QWidget" in stylesheet("Light")
    assert get_status_color("success", "Dark").name().lower() == "#10b981"
    assert get_status_color("failed", "Dark").name().lower() == "#ef4444"

