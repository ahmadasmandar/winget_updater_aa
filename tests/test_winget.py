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
    worker.progress_step.connect(lambda current, total, name: received.append((current, total, name)))
    with qtbot.waitSignal(worker.finished, timeout=2000): worker.start()
    assert received == [(1, 1, "Example")]
