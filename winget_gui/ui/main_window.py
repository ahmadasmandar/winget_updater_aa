import fnmatch
import logging
import os
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..config import ConfigManager, _validate_ids
from ..workers import InfoWorker, OperationWorker, PackageWorker
from ..winget import WingetBackend
from .exclusion_dialog import ExclusionDialog
from .info_dialog import show_info
from .theme import apply_theme, icon, resource_path, stylesheet

APP_VERSION = "1.0.0"


class QtLogHandler(logging.Handler, QtCore.QObject):
    message = QtCore.pyqtSignal(str)
    flushOnClose = False
    def __init__(self): logging.Handler.__init__(self); QtCore.QObject.__init__(self)
    def emit(self, record):
        try: self.message.emit(self.format(record))
        except RuntimeError: pass


class PackageModel(QtCore.QAbstractTableModel):
    headers = ["", "Name", "ID", "Version", "Available"]
    def __init__(self, parent=None): super().__init__(parent); self.rows = []
    def rowCount(self, parent=QtCore.QModelIndex()): return 0 if parent.isValid() else len(self.rows)
    def columnCount(self, parent=QtCore.QModelIndex()): return len(self.headers)
    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        row = self.rows[index.row()]; col = index.column()
        if role == QtCore.Qt.ItemDataRole.UserRole: return row.get("Id", "")
        if role == QtCore.Qt.ItemDataRole.CheckStateRole and col == 0: return row.get("checked", QtCore.Qt.CheckState.Unchecked)
        if role == QtCore.Qt.ItemDataRole.DisplayRole: return "" if col == 0 else [row.get("Name", ""), row.get("Id", ""), row.get("Version", ""), row.get("AvailableVersion", "")][col - 1]
        if role == QtCore.Qt.ItemDataRole.ToolTipRole: return row.get("last_status", "") or row.get("Id", "")
        return None
    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid() and index.column() == 0 and role == QtCore.Qt.ItemDataRole.CheckStateRole:
            self.rows[index.row()]["checked"] = QtCore.Qt.CheckState(value); self.dataChanged.emit(index, index, [role]); return True
        return False
    def flags(self, index): return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable | (QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEditable if index.column() == 0 else QtCore.Qt.ItemFlag.NoItemFlags)
    def headerData(self, section, orientation, role): return self.headers[section] if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole else None
    def set_rows(self, rows): self.beginResetModel(); self.rows = [dict(row, checked=QtCore.Qt.CheckState.Unchecked) for row in rows]; self.endResetModel()
    def ids(self, checked=False): return [row["Id"] for row in self.rows if not checked or QtCore.Qt.CheckState(row.get("checked", QtCore.Qt.CheckState.Unchecked)) == QtCore.Qt.CheckState.Checked]
    def row_for_id(self, package_id): return next((i for i, row in enumerate(self.rows) if row["Id"] == package_id), -1)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, backend=None):
        super().__init__(); self.backend = backend or WingetBackend(); self.logger = logging.getLogger("winget_gui"); self._last_results = {}; self._elapsed = QtCore.QElapsedTimer(); self._elapsed_timer = QtCore.QTimer(self); self._elapsed_timer.timeout.connect(self._update_elapsed); self.settings = QtCore.QSettings("WingetUpgrade", "WingetUpgrade")
        self.config_manager = ConfigManager(logger=self.logger, parent=self); self.config_manager.warning.connect(self._warn)
        self.config = self.config_manager.load(); self._workers = set(); self._worker = None; self._operation = None; self._info_worker = None
        self.setWindowTitle("Winget Package Manager"); self.resize(1400, 760); self.setStyleSheet(stylesheet()); self.setWindowIcon(QtGui.QIcon(resource_path("resources/updated.ico"))); apply_theme(QtWidgets.QApplication.instance(), self.settings.value("theme", "Dark"))
        self._build_ui(); self._setup_logging(); self._restore_state(); self._check_winget_version(); self.load_packages()

    def _build_ui(self):
        central = QtWidgets.QWidget(); self.setCentralWidget(central); layout = QtWidgets.QVBoxLayout(central)
        top = QtWidgets.QHBoxLayout(); self.search = QtWidgets.QLineEdit(); self.search.setPlaceholderText("Filter packages…"); top.addWidget(self.search)
        self.select_all = QtWidgets.QPushButton("Select all"); self.deselect_all = QtWidgets.QPushButton("Deselect all"); top.addWidget(self.select_all); top.addWidget(self.deselect_all); layout.addLayout(top)
        self.model = PackageModel(self); self.proxy = QtCore.QSortFilterProxyModel(self); self.proxy.setSourceModel(self.model); self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive); self.proxy.setFilterKeyColumn(-1)
        self.table = QtWidgets.QTableView(); self.table.setModel(self.proxy); self.table.setSortingEnabled(True); self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows); self.table.setAlternatingRowColors(False); self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch); self.table.clicked.connect(self._on_table_clicked); layout.addWidget(self.table)
        progress_row = QtWidgets.QHBoxLayout(); self.progress = QtWidgets.QProgressBar(); self.progress_label = QtWidgets.QLabel("Ready"); self.elapsed_label = QtWidgets.QLabel("Elapsed: 00:00"); self.command_label = QtWidgets.QLabel(""); self.command_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse); progress_row.addWidget(self.progress, 2); progress_row.addWidget(self.progress_label, 2); progress_row.addWidget(self.elapsed_label); progress_row.addWidget(self.command_label, 3); layout.addLayout(progress_row)
        buttons = [("upgrade_btn", "Upgrade selected", "go-up"), ("force_btn", "Force reinstall", "view-refresh"), ("all_btn", "Upgrade all", "go-up"), ("uninstall_btn", "Uninstall", "edit-delete"), ("exclude_btn", "Exclude", "list-remove"), ("manage_btn", "Exclusions", "preferences-system"), ("info_btn", "Info", "help-about"), ("logs_btn", "Logs", "folder-open"), ("refresh_btn", "Refresh", "view-refresh"), ("powershell_btn", "Upgrade PowerShell", "utilities-terminal"), ("cancel_btn", "Cancel", "process-stop")]
        row = QtWidgets.QHBoxLayout()
        for name, tip, ico in buttons:
            button = QtWidgets.QPushButton(tip); button.setIcon(icon(ico)); button.setToolTip(tip); setattr(self, name, button); row.addWidget(button)
        self.cancel_btn.setEnabled(False); layout.addLayout(row); self.status = QtWidgets.QLabel("Ready"); layout.addWidget(self.status)
        self.log_dock = QtWidgets.QDockWidget("Status / log", self); self.log_dock.setObjectName("statusLogDock"); self.log_text = QtWidgets.QPlainTextEdit(); self.log_text.setReadOnly(True); self.log_dock.setWidget(self.log_text); self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.search.textChanged.connect(lambda text: (self.logger.debug("Action filter text=%r", text), self.proxy.setFilterFixedString(text))); self.select_all.clicked.connect(lambda: self._invoke_action("select_all", lambda: self._check(True))); self.deselect_all.clicked.connect(lambda: self._invoke_action("deselect_all", lambda: self._check(False))); self.refresh_btn.clicked.connect(lambda: self._invoke_action("refresh", self.load_packages)); self.cancel_btn.clicked.connect(lambda: self._invoke_action("cancel", self._cancel_all)); self.info_btn.clicked.connect(lambda: self._invoke_action("info", self.show_info)); self.exclude_btn.clicked.connect(lambda: self._invoke_action("exclude", self.exclude_selected)); self.manage_btn.clicked.connect(lambda: self._invoke_action("manage_exclusions", self.manage_exclusions)); self.logs_btn.clicked.connect(lambda: self._invoke_action("open_logs", lambda: os.startfile(str(Path(self.config_manager.path).parent)))); self.upgrade_btn.clicked.connect(lambda: self._invoke_action("upgrade_selected", lambda: self._start_selected_action("upgrade"))); self.force_btn.clicked.connect(lambda: self._invoke_action("force_reinstall_selected", lambda: self._start_selected_action("force_reinstall"))); self.all_btn.clicked.connect(lambda: self._invoke_action("upgrade_all", self._start_all_action)); self.uninstall_btn.clicked.connect(lambda: self._invoke_action("uninstall_selected", lambda: self._start_selected_action("uninstall"))); self.powershell_btn.clicked.connect(lambda: self._invoke_action("upgrade_powershell", lambda: self.run_action("powershell", ["Microsoft.PowerShell"])))
        settings_menu = self.menuBar().addMenu("Settings"); theme_menu = settings_menu.addMenu("Theme"); group = QtGui.QActionGroup(self); group.setExclusive(True)
        for theme in ("Light", "Dark", "System"):
            action = theme_menu.addAction(theme); action.setCheckable(True); action.setChecked(self.settings.value("theme", "Dark") == theme); group.addAction(action); action.triggered.connect(lambda checked, value=theme: self.set_theme(value))
        about_action = self.menuBar().addAction("About"); about_action.triggered.connect(self.about)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.search.setFocus); QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.exclude_selected); QtGui.QShortcut(QtGui.QKeySequence("Space"), self, activated=self._toggle_current)

    def _restore_state(self):
        self.restoreGeometry(self.settings.value("geometry", b"")); self.restoreState(self.settings.value("state", b""))
    def closeEvent(self, event):
        self._cancel_all()
        for worker in list(self._workers): worker.wait(5000)
        self.logger.removeHandler(self.log_handler); self.logger.removeHandler(self.file_handler); self.log_handler.close(); self.file_handler.close()
        self.settings.setValue("geometry", self.saveGeometry()); self.settings.setValue("state", self.saveState()); event.accept()
    def _setup_logging(self):
        self.log_handler = QtLogHandler(); self.log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s")); self.log_handler.message.connect(self.log_text.appendPlainText); self.logger.setLevel(logging.DEBUG); self.logger.propagate = False; self.logger.addHandler(self.log_handler)
        log_dir = Path.cwd() / "logs"; log_dir.mkdir(parents=True, exist_ok=True); self.file_handler = logging.FileHandler(log_dir / "winget_gui_debug.log", encoding="utf-8"); self.file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s")); self.logger.addHandler(self.file_handler); self.logger.debug("Debug logging initialized; config=%s", self.config_manager.path)
    def _check_winget_version(self):
        try:
            version = self.backend.version(); numbers = tuple(int(part) for part in version.split(".")[:2] if part.isdigit())
            if numbers and numbers < (1, 4): self._warn(f"winget {version} may not support JSON output; text parsing will be used.")
        except Exception as exc: self.logger.warning("Could not check winget version: %s", exc)
    def _track(self, worker): self._workers.add(worker); self.logger.debug("Worker created: %s", type(worker).__name__); worker.finished.connect(worker.deleteLater); worker.finished.connect(lambda: self._workers.discard(worker)); return worker
    def _worker_running(self, worker):
        if worker is None: return False
        try: return worker.isRunning()
        except RuntimeError:
            self.logger.debug("Worker reference was already deleted: %s", type(worker).__name__)
            return False
    def _swap_worker(self, attr, worker):
        old = getattr(self, attr)
        if self._worker_running(old): self.logger.debug("Stopping existing worker: %s", type(old).__name__); old.cancel(); old.wait(3000); old.terminate(); old.wait(1000)
        setattr(self, attr, self._track(worker)); worker.finished.connect(lambda: setattr(self, attr, None) if getattr(self, attr, None) is worker else None); return worker
    def _set_loading(self, loading):
        for button in (self.upgrade_btn, self.force_btn, self.all_btn, self.uninstall_btn, self.exclude_btn, self.manage_btn, self.info_btn, self.logs_btn, self.refresh_btn, self.powershell_btn): button.setEnabled(not loading)
        self.cancel_btn.setEnabled(loading); self.progress_label.setText("Working…" if loading else "Ready")
        if loading: self._elapsed.start(); self._elapsed_timer.start(1000)
        else: self._elapsed_timer.stop(); self.elapsed_label.setText("Elapsed: 00:00")
    def _set_progress(self, mode, value=0, maximum=0): self.progress.setRange(0, 0 if mode == "busy" else max(1, maximum)); self.progress.setValue(value)
    def _update_elapsed(self): self.elapsed_label.setText(f"Elapsed: {self._elapsed.elapsed() // 1000:02d}s")
    def _on_progress_step(self, current, total, package_name): self._set_progress("determinate", current, total); self.progress_label.setText(f"Completed {current}/{total}: {package_name}"); self.elapsed_label.setText(f"Elapsed: {self._elapsed.elapsed() // 1000:02d}s")
    def load_packages(self):
        self._set_loading(True); self._set_progress("busy"); self.progress_label.setText("Refreshing package list…"); worker = self._swap_worker("_worker", PackageWorker(self.backend, self)); worker.packages_ready.connect(self._loaded); worker.error.connect(self._failed); worker.progress.connect(self.status.setText); worker.start()
    def _loaded(self, packages): self.model.set_rows([row for row in packages if not self._should_exclude(row)]); self._set_loading(False); self._set_progress("idle"); self.status.setText(f"Ready — {self.model.rowCount()} packages")
    def _failed(self, message): self._set_loading(False); self._set_progress("idle"); self.status.setText("Refresh failed"); self._warn(message)
    def _should_exclude(self, package):
        version = package.get("Version", "").lower(); package_id = package.get("Id", "").lower(); name = package.get("Name", "").lower()
        return self.config.get("exclude_unknown_versions", True) and version == "unknown" or any(fnmatch.fnmatch(name, p.lower()) or fnmatch.fnmatch(package_id, p.lower()) for p in self.config.get("excluded_patterns", [])) or any(package_id == value.lower() for value in self.config.get("excluded_ids", []))
    def _check(self, checked):
        for row in range(self.model.rowCount()): self.model.setData(self.model.index(row, 0), QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked, QtCore.Qt.ItemDataRole.CheckStateRole)
    def _toggle_current(self):
        index = self.table.currentIndex(); source = self.proxy.mapToSource(index)
        if source.isValid(): self.model.setData(source, QtCore.Qt.CheckState.Unchecked if self.model.data(source, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Checked else QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole)
    def _on_table_clicked(self, index):
        self.logger.debug("Table clicked: proxy_row=%d proxy_column=%d", index.row(), index.column())
        if index.column() != 0:
            source = self.proxy.mapToSource(index); current = self.model.data(self.model.index(source.row(), 0), QtCore.Qt.ItemDataRole.CheckStateRole)
            self.model.setData(self.model.index(source.row(), 0), QtCore.Qt.CheckState.Unchecked if current == QtCore.Qt.CheckState.Checked else QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole)
    def _invoke_action(self, name, callback):
        self.logger.info("Action requested: %s", name)
        try:
            return callback()
        except Exception:
            self.logger.exception("Action failed: %s", name)
            raise
    def checked_ids(self):
        checked = self.model.ids(True)
        selected = [self.model.data(self.proxy.mapToSource(i), QtCore.Qt.ItemDataRole.UserRole) for i in self.table.selectionModel().selectedRows()]
        result = checked or selected
        self.logger.debug("Selection resolved: checked=%r selected=%r result=%r", checked, selected, result)
        return result

    def selected_ids(self):
        result = [self.model.data(self.proxy.mapToSource(i), QtCore.Qt.ItemDataRole.UserRole) for i in self.table.selectionModel().selectedRows()]
        self.logger.debug("Selected rows resolved: %r", result)
        return result

    def _start_selected_action(self, action):
        self.logger.debug("Selected action requested: %s", action)
        self.run_action(action, self.checked_ids())

    def _start_all_action(self):
        self.logger.debug("Upgrade all requested")
        self.run_action("upgrade", self.model.ids())
    def exclude_selected(self):
        ids = self.checked_ids() or self.selected_ids(); valid = [value for value in ids if _validate_ids.fullmatch(value or "")]
        if valid:
            self.config["excluded_ids"] = list(dict.fromkeys(self.config.get("excluded_ids", []) + valid)); self.config_manager.save(self.config); self.model.set_rows([row for row in self.model.rows if not self._should_exclude(row)])
    def manage_exclusions(self):
        dialog = ExclusionDialog(self.config, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.config["excluded_ids"], self.config["excluded_patterns"] = dialog.values(); self.config_manager.save(self.config); self.model.set_rows([row for row in self.model.rows if not self._should_exclude(row)])
    def run_action(self, action, ids):
        original_ids = list(ids)
        ids = [value for value in ids if _validate_ids.fullmatch(value or "")]
        self.logger.debug("run_action action=%s original_ids=%r valid_ids=%r", action, original_ids, ids)
        if not ids:
            self.status.setText("No valid package selected"); self.logger.warning("Action %s did not start: no valid package IDs", action); return
        commands = {"upgrade": ["upgrade"], "force_reinstall": ["install", "--force"], "uninstall": ["uninstall"], "powershell": ["install", "--source", "winget"]}
        ops = [([*commands[action], "--id", package_id, "-e", "--accept-source-agreements", "--accept-package-agreements"], package_id, action.replace("_", " ").title(), next((row.get("Name", package_id) for row in self.model.rows if row.get("Id") == package_id), package_id)) for package_id in ids]
        self._last_results = {}; self._set_loading(True); self._set_progress("determinate", 0, len(ops)); worker = self._swap_worker("_operation", OperationWorker(ops, self.backend, self)); worker.progress.connect(self._on_command_progress); worker.progress_step.connect(self._on_progress_step); worker.progress_count.connect(lambda value, maximum: self._set_progress("determinate", value, maximum)); worker.package_result.connect(lambda package_id, status, output: (self.logger.debug("Package result id=%s status=%s output=%r", package_id, status, output[-500:]), self._last_results.__setitem__(package_id, status))); worker.finished_all.connect(lambda *counts: self._operation_done(action, counts)); self.logger.info("Starting action=%s operations=%d", action, len(ops)); worker.start()
    def _on_command_progress(self, message):
        self.logger.debug("Worker progress: %s", message); current, _, command = message.partition(" | "); self.status.setText(current); self.progress_label.setText(current); self.command_label.setText(command)
    def _operation_done(self, action, counts):
        self.logger.info("Action complete=%s counts=%r results=%r", action, counts, self._last_results); self._set_loading(False); self._set_progress("idle"); self.status.setText(f"{action} complete: {counts[0]} succeeded, {counts[1]} failed")
        # Keep the current model intact after an operation; only affected rows are changed below.
        for package_id, status in self._last_results.items():
            row = self.model.row_for_id(package_id)
            if row < 0: continue
            if action == "uninstall" and status == "success": self.model.beginRemoveRows(QtCore.QModelIndex(), row, row); self.model.rows.pop(row); self.model.endRemoveRows()
            else: self.model.rows[row]["last_status"] = status; index = self.model.index(row, 0); self.model.dataChanged.emit(index, self.model.index(row, self.model.columnCount() - 1), [QtCore.Qt.ItemDataRole.ToolTipRole])
    def show_info(self):
        ids = self.checked_ids() or self.selected_ids()
        if len(ids) != 1 or self._worker_running(self._info_worker): return
        self._set_loading(True); self.info_btn.setEnabled(False); worker = self._swap_worker("_info_worker", InfoWorker(ids[0], self.backend, self)); worker.result_ready.connect(lambda package_id, output: (self._set_loading(False), show_info(self, package_id, output))); worker.error.connect(self._failed); worker.start()
    def _cancel_all(self):
        self.logger.info("Cancel requested for workers=%s", [type(worker).__name__ for worker in self._workers])
        for worker in list(self._workers): worker.cancel()
    def set_theme(self, theme):
        self.logger.info("Theme changed: %s", theme); self.settings.setValue("theme", theme); apply_theme(QtWidgets.QApplication.instance(), theme)
    def _warn(self, message): self.logger.warning(message); QtWidgets.QMessageBox.warning(self, "Winget GUI", message)
    def about(self): QtWidgets.QMessageBox.about(self, "About", f"Winget Package Manager {APP_VERSION}")
