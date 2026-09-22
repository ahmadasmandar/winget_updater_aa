import fnmatch
import html
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..config import ConfigManager, _validate_ids
from ..winget import WingetBackend
from ..workers import InfoWorker, OperationWorker, PackageWorker
from .exclusion_dialog import ExclusionDialog
from .info_dialog import show_info
from .theme import apply_theme, get_status_color, icon, resource_path, resolve_theme_mode, stylesheet

APP_VERSION = "1.0.0"


class QtLogHandler(logging.Handler, QtCore.QObject):
    message_html = QtCore.pyqtSignal(str)
    flushOnClose = False

    def __init__(self, get_theme_mode_fn=None):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        self.get_theme_mode = get_theme_mode_fn or (lambda: "Dark")

    def emit(self, record):
        try:
            mode = resolve_theme_mode(self.get_theme_mode())
            dt = datetime.fromtimestamp(record.created)
            time_str = dt.strftime("%H:%M:%S") + f".{int(record.msecs):03d}"
            level = record.levelname
            time_color = "#64748B" if mode == "Light" else "#94A3B8"
            module_name = record.name.split(".")[-1]

            if level == "INFO":
                lvl_color = "#16A34A" if mode == "Light" else "#22C55E"
            elif level in ("WARNING", "WARN"):
                lvl_color = "#CA8A04" if mode == "Light" else "#FACC15"
            elif level in ("ERROR", "CRITICAL"):
                lvl_color = "#DC2626" if mode == "Light" else "#EF4444"
            else:
                lvl_color = "#475569" if mode == "Light" else "#94A3B8"

            msg = html.escape(record.getMessage())
            formatted = (
                f'<span style="color: {time_color}; font-size: 9.5pt;">{time_str}</span> '
                f'<span style="color: {lvl_color}; font-weight: bold; font-size: 9.5pt;">[{level:5s}]</span> '
                f'<span style="color: #64748B; font-size: 9.5pt;">[{module_name}]</span> '
                f'<span style="font-size: 11pt;">{msg}</span>'
            )

            if record.exc_info:
                exc_text = "".join(traceback.format_exception(*record.exc_info))
                exc_escaped = html.escape(exc_text)
                err_bg = "#FEE2E2" if mode == "Light" else "#2D151B"
                err_color = "#B91C1C" if mode == "Light" else "#FCA5A5"
                formatted += (
                    f'<pre style="margin: 4px 0 6px 20px; padding: 8px; background: {err_bg}; '
                    f'color: {err_color}; border-radius: 4px; font-family: \'Fira Code\', \'Fira Mono\', monospace; font-size: 10pt;">'
                    f'{exc_escaped}</pre>'
                )

            self.message_html.emit(formatted)
        except RuntimeError:
            pass


class PackageModel(QtCore.QAbstractTableModel):
    headers = ["", "Package Name", "Package ID", "Installed", "Available", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.parent_window = parent

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.headers)

    def _theme_mode(self):
        if self.parent_window and hasattr(self.parent_window, "current_theme"):
            return self.parent_window.current_theme
        return "Dark"

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.rows):
            return None

        row = self.rows[index.row()]
        col = index.column()
        theme_mode = self._theme_mode()

        if role == QtCore.Qt.ItemDataRole.UserRole:
            return row.get("Id", "")

        if role == QtCore.Qt.ItemDataRole.CheckStateRole and col == 0:
            return row.get("checked", QtCore.Qt.CheckState.Unchecked)

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ""
            if col == 1:
                return row.get("Name", "")
            if col == 2:
                return row.get("Id", "")
            if col == 3:
                return row.get("Version", "")
            if col == 4:
                return row.get("AvailableVersion", "")
            if col == 5:
                status = row.get("last_status", "")
                if status == "in_progress":
                    action_name = row.get("current_action", "Updating")
                    return f"● {action_name}…"
                if status == "success":
                    return "✓ Upgraded"
                if status == "failed":
                    return "✕ Failed"
                if status == "skipped":
                    return "✓ Up to date"
                if status == "mismatch":
                    return "⚠ Mismatch"
                if row.get("AvailableVersion"):
                    return "● Update available"
                return "Installed"

        if role == QtCore.Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                return get_status_color("default", theme_mode)
            if col in (2, 3):
                return get_status_color("excluded", theme_mode)
            if col == 4:
                return get_status_color("available", theme_mode)
            if col == 5:
                status = row.get("last_status", "")
                if status:
                    return get_status_color(status, theme_mode)
                if row.get("AvailableVersion"):
                    return get_status_color("available", theme_mode)
                return get_status_color("default", theme_mode)

        if role == QtCore.Qt.ItemDataRole.FontRole:
            if col == 1:
                font = QtGui.QFont()
                font.setWeight(QtGui.QFont.Weight.DemiBold)
                return font
            if col == 5:
                font = QtGui.QFont()
                font.setWeight(QtGui.QFont.Weight.DemiBold)
                return font

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return QtCore.Qt.AlignmentFlag.AlignCenter
            return QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft

        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            name = row.get("Name", "")
            pkg_id = row.get("Id", "")
            ver = row.get("Version", "")
            avail = row.get("AvailableVersion", "")
            status = row.get("last_status", "") or ("Update Available" if avail else "Installed")
            return f"Package: {name}\nID: {pkg_id}\nInstalled: {ver}\nAvailable: {avail}\nStatus: {status}"

        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if index.isValid() and index.column() == 0 and role == QtCore.Qt.ItemDataRole.CheckStateRole:
            self.rows[index.row()]["checked"] = QtCore.Qt.CheckState(value)
            self.dataChanged.emit(index, index, [role])
            if self.parent_window and hasattr(self.parent_window, "_update_selection_count"):
                self.parent_window._update_selection_count()
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        base_flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            return base_flags | QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEditable
        return base_flags

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = [dict(row, checked=QtCore.Qt.CheckState.Unchecked) for row in rows]
        self.endResetModel()
        if self.parent_window and hasattr(self.parent_window, "_update_selection_count"):
            self.parent_window._update_selection_count()

    def ids(self, checked=False):
        return [
            row["Id"]
            for row in self.rows
            if not checked
            or QtCore.Qt.CheckState(row.get("checked", QtCore.Qt.CheckState.Unchecked)) == QtCore.Qt.CheckState.Checked
        ]

    def row_for_id(self, package_id):
        return next((i for i, row in enumerate(self.rows) if row["Id"] == package_id), -1)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, backend=None):
        super().__init__()
        self.backend = backend or WingetBackend()
        self.logger = logging.getLogger("winget_gui")
        self._last_results = {}
        self._elapsed = QtCore.QElapsedTimer()
        self._elapsed_timer = QtCore.QTimer(self)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self.settings = QtCore.QSettings("WingetUpgrade", "WingetUpgrade")
        self.current_theme = self.settings.value("theme", "Dark")
        raw_show_console = self.settings.value("show_console", True)
        if isinstance(raw_show_console, str):
            self.show_console = raw_show_console.lower() in ("true", "1")
        else:
            self.show_console = bool(raw_show_console)

        self.config_manager = ConfigManager(logger=self.logger, parent=self)
        self.config_manager.warning.connect(self._warn)
        self.config = self.config_manager.load()

        self._workers = set()
        self._worker = None
        self._operation = None
        self._info_worker = None

        self.setWindowTitle("Winget Package Manager")
        self.resize(1400, 780)
        self.setWindowIcon(QtGui.QIcon(resource_path("resources/updated.ico")))
        apply_theme(QtWidgets.QApplication.instance(), self.current_theme)

        self._build_ui()
        self._setup_logging()
        self._restore_state()
        self._check_winget_version()
        self.load_packages()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # ==================== TOP BAR: SEARCH & SELECTION ====================
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.setSpacing(8)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("🔍  Search packages by name or ID (Ctrl+F)…")
        self.search.setClearButtonEnabled(True)
        top_bar.addWidget(self.search, 4)

        self.select_all = QtWidgets.QPushButton("Select All")
        self.select_all.setObjectName("accentBtn")
        self.deselect_all = QtWidgets.QPushButton("Deselect All")
        top_bar.addWidget(self.select_all)
        top_bar.addWidget(self.deselect_all)

        self.selection_badge = QtWidgets.QLabel("0 selected (0 total)")
        self.selection_badge.setObjectName("badgeLabel")
        top_bar.addWidget(self.selection_badge)

        main_layout.addLayout(top_bar)

        # ==================== ACTION TOOLBAR ====================
        action_layout = QtWidgets.QHBoxLayout()
        action_layout.setSpacing(6)

        self.upgrade_btn = QtWidgets.QPushButton("  Upgrade Selected")
        self.upgrade_btn.setIcon(icon("go-up"))
        self.upgrade_btn.setObjectName("primaryBtn")
        action_layout.addWidget(self.upgrade_btn)

        self.all_btn = QtWidgets.QPushButton("  Upgrade All")
        self.all_btn.setIcon(icon("go-up"))
        self.all_btn.setObjectName("accentBtn")
        action_layout.addWidget(self.all_btn)

        self.refresh_btn = QtWidgets.QPushButton("  Refresh")
        self.refresh_btn.setIcon(icon("view-refresh"))
        action_layout.addWidget(self.refresh_btn)

        self.force_btn = QtWidgets.QPushButton("  Force Reinstall")
        self.force_btn.setIcon(icon("view-refresh"))
        action_layout.addWidget(self.force_btn)

        self.uninstall_btn = QtWidgets.QPushButton("  Uninstall")
        self.uninstall_btn.setIcon(icon("edit-delete"))
        self.uninstall_btn.setObjectName("dangerBtn")
        action_layout.addWidget(self.uninstall_btn)

        self.info_btn = QtWidgets.QPushButton("  Details")
        self.info_btn.setIcon(icon("help-about"))
        action_layout.addWidget(self.info_btn)

        self.exclude_btn = QtWidgets.QPushButton("  Exclude")
        self.exclude_btn.setIcon(icon("list-remove"))
        action_layout.addWidget(self.exclude_btn)

        self.manage_btn = QtWidgets.QPushButton("  Exclusions")
        self.manage_btn.setIcon(icon("preferences-system"))
        action_layout.addWidget(self.manage_btn)

        self.powershell_btn = QtWidgets.QPushButton("  PowerShell")
        self.powershell_btn.setIcon(icon("utilities-terminal"))
        action_layout.addWidget(self.powershell_btn)

        self.logs_btn = QtWidgets.QPushButton("  Logs")
        self.logs_btn.setIcon(icon("folder-open"))
        action_layout.addWidget(self.logs_btn)

        action_layout.addStretch()

        self.cancel_btn = QtWidgets.QPushButton("  Cancel")
        self.cancel_btn.setIcon(icon("process-stop"))
        self.cancel_btn.setObjectName("dangerBtn")
        self.cancel_btn.setEnabled(False)
        action_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(action_layout)

        # ==================== PACKAGES TABLE ====================
        self.model = PackageModel(self)
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 38)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(5, 160)

        self.table.clicked.connect(self._on_table_clicked)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self.table)

        # ==================== PROGRESS & STATUS ROW ====================
        progress_box = QtWidgets.QHBoxLayout()
        progress_box.setSpacing(10)

        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setStyleSheet("color: #10B981; font-size: 14pt; font-weight: bold;")
        progress_box.addWidget(self.status_dot)

        self.status = QtWidgets.QLabel("Ready")
        self.status.setStyleSheet("font-weight: 600;")
        progress_box.addWidget(self.status, 2)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(True)
        progress_box.addWidget(self.progress, 3)

        self.progress_label = QtWidgets.QLabel("Ready")
        self.progress_label.setObjectName("mutedLabel")
        progress_box.addWidget(self.progress_label, 2)

        self.elapsed_label = QtWidgets.QLabel("⏱ 00:00")
        self.elapsed_label.setObjectName("badgeLabel")
        progress_box.addWidget(self.elapsed_label)

        self.command_label = QtWidgets.QLabel("")
        self.command_label.setObjectName("commandLabel")
        self.command_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        progress_box.addWidget(self.command_label, 3)

        main_layout.addLayout(progress_box)

        # ==================== LOG DOCK ====================
        self.log_dock = QtWidgets.QDockWidget("Activity & Terminal Logs", self)
        self.log_dock.setObjectName("statusLogDock")
        dock_container = QtWidgets.QWidget()
        dock_layout = QtWidgets.QVBoxLayout(dock_container)
        dock_layout.setContentsMargins(6, 6, 6, 6)
        dock_layout.setSpacing(6)

        log_top = QtWidgets.QHBoxLayout()
        clear_logs_btn = QtWidgets.QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(self._clear_logs)
        copy_logs_btn = QtWidgets.QPushButton("Copy Logs")
        copy_logs_btn.clicked.connect(self._copy_logs)
        log_top.addWidget(clear_logs_btn)
        log_top.addWidget(copy_logs_btn)
        log_top.addStretch()
        dock_layout.addLayout(log_top)

        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        log_font = QtGui.QFont()
        log_font.setFamilies(["Fira Code", "Fira Mono", "Cascadia Code", "Consolas", "Courier New"])
        log_font.setPointSize(11)
        self.log_text.setFont(log_font)
        self.log_text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.log_text.textChanged.connect(
            lambda: self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        )
        dock_layout.addWidget(self.log_text)

        self.log_dock.setWidget(dock_container)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

        # ==================== EVENT CONNECTIONS ====================
        self.search.textChanged.connect(
            lambda text: (
                self.logger.debug("Action filter text=%r", text),
                self.proxy.setFilterFixedString(text),
                self._update_selection_count(),
            )
        )
        self.select_all.clicked.connect(lambda: self._invoke_action("select_all", lambda: self._check(True)))
        self.deselect_all.clicked.connect(lambda: self._invoke_action("deselect_all", lambda: self._check(False)))
        self.refresh_btn.clicked.connect(lambda: self._invoke_action("refresh", self.load_packages))
        self.cancel_btn.clicked.connect(lambda: self._invoke_action("cancel", self._cancel_all))
        self.info_btn.clicked.connect(lambda: self._invoke_action("info", self.show_info))
        self.exclude_btn.clicked.connect(lambda: self._invoke_action("exclude", self.exclude_selected))
        self.manage_btn.clicked.connect(lambda: self._invoke_action("manage_exclusions", self.manage_exclusions))
        self.logs_btn.clicked.connect(
            lambda: self._invoke_action(
                "open_logs", lambda: os.startfile(str(Path(self.config_manager.path).parent))
            )
        )
        self.upgrade_btn.clicked.connect(
            lambda: self._invoke_action("upgrade_selected", lambda: self._start_selected_action("upgrade"))
        )
        self.force_btn.clicked.connect(
            lambda: self._invoke_action(
                "force_reinstall_selected", lambda: self._start_selected_action("force_reinstall")
            )
        )
        self.all_btn.clicked.connect(lambda: self._invoke_action("upgrade_all", self._start_all_action))
        self.uninstall_btn.clicked.connect(
            lambda: self._invoke_action("uninstall_selected", lambda: self._start_selected_action("uninstall"))
        )
        self.powershell_btn.clicked.connect(
            lambda: self._invoke_action(
                "upgrade_powershell", lambda: self.run_action("powershell", ["Microsoft.PowerShell"])
            )
        )

        # ==================== MENUS & SHORTCUTS ====================
        settings_menu = self.menuBar().addMenu("Settings")
        theme_menu = settings_menu.addMenu("Theme")
        group = QtGui.QActionGroup(self)
        group.setExclusive(True)

        for theme in ("Dark", "Light", "System"):
            action = theme_menu.addAction(theme)
            action.setCheckable(True)
            action.setChecked(self.settings.value("theme", "Dark") == theme)
            group.addAction(action)
            action.triggered.connect(lambda checked, value=theme: self.set_theme(value))

        settings_menu.addSeparator()
        self.console_action = settings_menu.addAction("Show Terminal Window During Operations")
        self.console_action.setCheckable(True)
        self.console_action.setChecked(self.show_console)
        self.console_action.toggled.connect(self._toggle_show_console)

        about_action = self.menuBar().addAction("About")
        about_action.triggered.connect(self.about)

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.search.setFocus)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.exclude_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Space"), self, activated=self._toggle_current)

    def _clear_logs(self):
        self.log_text.clear()

    def _copy_logs(self):
        QtGui.QGuiApplication.clipboard().setText(self.log_text.toPlainText())

    def _update_selection_count(self):
        checked_count = len(self.model.ids(True))
        total_count = self.model.rowCount()
        self.selection_badge.setText(f"{checked_count} selected ({total_count} total)")

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        source_idx = self.proxy.mapToSource(index)
        row = self.model.rows[source_idx.row()]
        pkg_id = row.get("Id", "")
        pkg_name = row.get("Name", "")

        menu = QtWidgets.QMenu(self)
        upgrade_act = menu.addAction(icon("go-up"), f"Upgrade '{pkg_name}'")
        force_act = menu.addAction(icon("view-refresh"), f"Force Reinstall '{pkg_name}'")
        uninstall_act = menu.addAction(icon("edit-delete"), f"Uninstall '{pkg_name}'")
        menu.addSeparator()
        info_act = menu.addAction(icon("help-about"), "View Details…")
        exclude_act = menu.addAction(icon("list-remove"), "Exclude Package")
        menu.addSeparator()
        copy_id_act = menu.addAction("Copy Package ID")
        copy_name_act = menu.addAction("Copy Package Name")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == upgrade_act:
            self.run_action("upgrade", [pkg_id])
        elif action == force_act:
            self.run_action("force_reinstall", [pkg_id])
        elif action == uninstall_act:
            self.run_action("uninstall", [pkg_id])
        elif action == info_act:
            self._fetch_and_show_info(pkg_id)
        elif action == exclude_act:
            self.config["excluded_ids"] = list(dict.fromkeys(self.config.get("excluded_ids", []) + [pkg_id]))
            self.config_manager.save(self.config)
            self.model.set_rows([r for r in self.model.rows if not self._should_exclude(r)])
        elif action == copy_id_act:
            QtGui.QGuiApplication.clipboard().setText(pkg_id)
        elif action == copy_name_act:
            QtGui.QGuiApplication.clipboard().setText(pkg_name)

    def _on_table_double_clicked(self, index):
        if not index.isValid():
            return
        source_idx = self.proxy.mapToSource(index)
        pkg_id = self.model.rows[source_idx.row()].get("Id", "")
        if pkg_id:
            self._fetch_and_show_info(pkg_id)

    def _fetch_and_show_info(self, package_id):
        if self._worker_running(self._info_worker):
            return
        self._set_loading(True)
        worker = self._swap_worker("_info_worker", InfoWorker(package_id, self.backend, self))
        worker.result_ready.connect(lambda pid, output: (self._set_loading(False), show_info(self, pid, output)))
        worker.error.connect(self._failed)
        worker.start()

    def _restore_state(self):
        self.restoreGeometry(self.settings.value("geometry", b""))
        self.restoreState(self.settings.value("state", b""))

    def closeEvent(self, event):
        self._cancel_all()
        for worker in list(self._workers):
            worker.wait(5000)
        self.logger.removeHandler(self.log_handler)
        self.logger.removeHandler(self.file_handler)
        self.log_handler.close()
        self.file_handler.close()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("state", self.saveState())
        event.accept()

    def _setup_logging(self):
        self.log_handler = QtLogHandler(lambda: self.current_theme)
        self.log_handler.message_html.connect(self.log_text.appendHtml)
        self.log_handler.setLevel(logging.DEBUG)

        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.file_handler = logging.FileHandler(log_dir / "winget_gui_debug.log", encoding="utf-8")
        self.file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        self.file_handler.setLevel(logging.DEBUG)

        # Attach to root 'winget_gui' logger so workers, backend, and config all stream here
        root_app_logger = logging.getLogger("winget_gui")
        root_app_logger.setLevel(logging.DEBUG)
        root_app_logger.addHandler(self.log_handler)
        root_app_logger.addHandler(self.file_handler)

        def _handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            self.logger.critical("Uncaught Exception Encountered:", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = _handle_exception
        self.logger.info("Winget Package Manager logging initialized (Fira Code font active).")
        self.logger.debug("Active configuration path: %s", self.config_manager.path)

    def _check_winget_version(self):
        try:
            version = self.backend.version()
            numbers = tuple(int(part) for part in version.split(".")[:2] if part.isdigit())
            if numbers and numbers < (1, 4):
                self._warn(f"winget {version} may not support JSON output; text parsing will be used.")
        except Exception as exc:
            self.logger.warning("Could not check winget version: %s", exc)

    def _track(self, worker):
        self._workers.add(worker)
        self.logger.debug("Worker created: %s", type(worker).__name__)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: self._workers.discard(worker))
        return worker

    def _worker_running(self, worker):
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            self.logger.debug("Worker reference was already deleted: %s", type(worker).__name__)
            return False

    def _swap_worker(self, attr, worker):
        old = getattr(self, attr)
        if self._worker_running(old):
            self.logger.debug("Stopping existing worker: %s", type(old).__name__)
            old.cancel()
            old.wait(3000)
            old.terminate()
            old.wait(1000)
        setattr(self, attr, self._track(worker))
        worker.finished.connect(
            lambda: setattr(self, attr, None) if getattr(self, attr, None) is worker else None
        )
        return worker

    def _set_loading(self, loading):
        for button in (
            self.upgrade_btn,
            self.force_btn,
            self.all_btn,
            self.uninstall_btn,
            self.exclude_btn,
            self.manage_btn,
            self.info_btn,
            self.logs_btn,
            self.refresh_btn,
            self.powershell_btn,
        ):
            button.setEnabled(not loading)
        self.cancel_btn.setEnabled(loading)
        self.progress_label.setText("Working…" if loading else "Ready")
        if loading:
            self.status_dot.setStyleSheet("color: #38BDF8; font-size: 14pt; font-weight: bold;")
            self._elapsed.start()
            self._elapsed_timer.start(1000)
        else:
            self.status_dot.setStyleSheet("color: #10B981; font-size: 14pt; font-weight: bold;")
            self._elapsed_timer.stop()
            self.elapsed_label.setText("⏱ 00:00")

    def _set_progress(self, mode, value=0, maximum=0):
        self.progress.setRange(0, 0 if mode == "busy" else max(1, maximum))
        self.progress.setValue(value)

    def _update_elapsed(self):
        self.elapsed_label.setText(f"⏱ {self._elapsed.elapsed() // 1000:02d}s")

    def _on_progress_step(self, current, total, package_name):
        self._set_progress("determinate", current, total)
        self.progress_label.setText(f"Completed {current}/{total}: {package_name}")
        self.elapsed_label.setText(f"⏱ {self._elapsed.elapsed() // 1000:02d}s")

    def load_packages(self):
        self._set_loading(True)
        self._set_progress("busy")
        self.progress_label.setText("Refreshing package list…")
        self.status.setText("Scanning installed packages & available updates…")
        worker = self._swap_worker("_worker", PackageWorker(self.backend, self))
        worker.packages_ready.connect(self._loaded)
        worker.error.connect(self._failed)
        worker.progress.connect(self.status.setText)
        worker.start()

    def _loaded(self, packages):
        self.model.set_rows([row for row in packages if not self._should_exclude(row)])
        self._set_loading(False)
        self._set_progress("idle")
        count = self.model.rowCount()
        self.status.setText(f"Ready — {count} package{'s' if count != 1 else ''} available for update")
        self._update_selection_count()

    def _failed(self, message):
        self._set_loading(False)
        self._set_progress("idle")
        self.status_dot.setStyleSheet("color: #EF4444; font-size: 14pt; font-weight: bold;")
        self.status.setText("Refresh failed")
        self._warn(message)

    def _should_exclude(self, package):
        version = package.get("Version", "").lower()
        package_id = package.get("Id", "").lower()
        name = package.get("Name", "").lower()
        return (
            (self.config.get("exclude_unknown_versions", True) and version == "unknown")
            or any(
                fnmatch.fnmatch(name, p.lower()) or fnmatch.fnmatch(package_id, p.lower())
                for p in self.config.get("excluded_patterns", [])
            )
            or any(package_id == value.lower() for value in self.config.get("excluded_ids", []))
        )

    def _check(self, checked):
        for row in range(self.model.rowCount()):
            self.model.setData(
                self.model.index(row, 0),
                QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked,
                QtCore.Qt.ItemDataRole.CheckStateRole,
            )

    def _toggle_current(self):
        index = self.table.currentIndex()
        source = self.proxy.mapToSource(index)
        if source.isValid():
            self.model.setData(
                source,
                QtCore.Qt.CheckState.Unchecked
                if self.model.data(source, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Checked
                else QtCore.Qt.CheckState.Checked,
                QtCore.Qt.ItemDataRole.CheckStateRole,
            )

    def _on_table_clicked(self, index):
        self.logger.debug("Table clicked: proxy_row=%d proxy_column=%d", index.row(), index.column())
        if index.column() != 0:
            source = self.proxy.mapToSource(index)
            current = self.model.data(self.model.index(source.row(), 0), QtCore.Qt.ItemDataRole.CheckStateRole)
            self.model.setData(
                self.model.index(source.row(), 0),
                QtCore.Qt.CheckState.Unchecked
                if current == QtCore.Qt.CheckState.Checked
                else QtCore.Qt.CheckState.Checked,
                QtCore.Qt.ItemDataRole.CheckStateRole,
            )

    def _invoke_action(self, name, callback):
        self.logger.info("Action requested: %s", name)
        try:
            return callback()
        except Exception:
            self.logger.exception("Action failed: %s", name)
            raise

    def checked_ids(self):
        checked = self.model.ids(True)
        selected = [
            self.model.data(self.proxy.mapToSource(i), QtCore.Qt.ItemDataRole.UserRole)
            for i in self.table.selectionModel().selectedRows()
        ]
        result = checked or selected
        self.logger.debug("Selection resolved: checked=%r selected=%r result=%r", checked, selected, result)
        return result

    def selected_ids(self):
        result = [
            self.model.data(self.proxy.mapToSource(i), QtCore.Qt.ItemDataRole.UserRole)
            for i in self.table.selectionModel().selectedRows()
        ]
        self.logger.debug("Selected rows resolved: %r", result)
        return result

    def _start_selected_action(self, action):
        self.logger.debug("Selected action requested: %s", action)
        self.run_action(action, self.checked_ids())

    def _start_all_action(self):
        self.logger.debug("Upgrade all requested")
        self.run_action("upgrade", self.model.ids())

    def exclude_selected(self):
        ids = self.checked_ids() or self.selected_ids()
        valid = [value for value in ids if _validate_ids.fullmatch(value or "")]
        if valid:
            self.config["excluded_ids"] = list(dict.fromkeys(self.config.get("excluded_ids", []) + valid))
            self.config_manager.save(self.config)
            self.model.set_rows([row for row in self.model.rows if not self._should_exclude(row)])

    def manage_exclusions(self):
        dialog = ExclusionDialog(self.config, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.config["excluded_ids"], self.config["excluded_patterns"] = dialog.values()
            self.config_manager.save(self.config)
            self.model.set_rows([row for row in self.model.rows if not self._should_exclude(row)])

    def run_action(self, action, ids):
        original_ids = list(ids)
        ids = [value for value in ids if _validate_ids.fullmatch(value or "")]
        self.logger.debug("run_action action=%s original_ids=%r valid_ids=%r", action, original_ids, ids)
        if not ids:
            self.status.setText("No valid package selected")
            self.logger.warning("Action %s did not start: no valid package IDs", action)
            return

        commands = {
            "upgrade": ["upgrade"],
            "force_reinstall": ["install", "--force"],
            "uninstall": ["uninstall"],
            "powershell": ["install", "--source", "winget"],
        }
        ops = [
            (
                [
                    *commands[action],
                    "--id",
                    package_id,
                    "-e",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ],
                package_id,
                action.replace("_", " ").title(),
                next((row.get("Name", package_id) for row in self.model.rows if row.get("Id") == package_id), package_id),
            )
            for package_id in ids
        ]

        self._last_results = {}
        self._set_loading(True)
        self._set_progress("determinate", 0, len(ops))

        worker = self._swap_worker("_operation", OperationWorker(ops, self.backend, self, visible=self.show_console))
        worker.progress.connect(self._on_command_progress)
        worker.progress_step.connect(self._on_progress_step)
        worker.progress_count.connect(lambda value, maximum: self._set_progress("determinate", value, maximum))
        worker.package_started.connect(self._on_package_started)
        worker.package_result.connect(self._on_package_result)
        worker.finished_all.connect(lambda *counts: self._operation_done(action, counts))
        self.logger.info("Starting action=%s operations=%d", action, len(ops))
        worker.start()

    def _on_package_started(self, package_id, action_label):
        row = self.model.row_for_id(package_id)
        if row >= 0:
            self.model.rows[row]["last_status"] = "in_progress"
            self.model.rows[row]["current_action"] = action_label
            index = self.model.index(row, 0)
            self.model.dataChanged.emit(
                index,
                self.model.index(row, self.model.columnCount() - 1),
                [
                    QtCore.Qt.ItemDataRole.DisplayRole,
                    QtCore.Qt.ItemDataRole.ForegroundRole,
                    QtCore.Qt.ItemDataRole.ToolTipRole,
                ],
            )

    def _on_package_result(self, package_id, status, output):
        self.logger.debug("Package result id=%s status=%s output=%r", package_id, status, output[-500:])
        self._last_results[package_id] = status
        row = self.model.row_for_id(package_id)
        if row >= 0:
            self.model.rows[row]["last_status"] = status
            index = self.model.index(row, 0)
            self.model.dataChanged.emit(
                index,
                self.model.index(row, self.model.columnCount() - 1),
                [
                    QtCore.Qt.ItemDataRole.DisplayRole,
                    QtCore.Qt.ItemDataRole.ForegroundRole,
                    QtCore.Qt.ItemDataRole.ToolTipRole,
                ],
            )

    def _on_command_progress(self, message):
        self.logger.debug("Worker progress: %s", message)
        current, _, command = message.partition(" | ")
        self.status.setText(current)
        self.progress_label.setText(current)
        self.command_label.setText(command)

    def _operation_done(self, action, counts):
        self.logger.info("Action complete=%s counts=%r results=%r", action, counts, self._last_results)
        self._set_loading(False)
        self._set_progress("idle")
        succeeded, failed, skipped, mismatch = counts
        self.status.setText(
            f"{action.replace('_', ' ').title()} complete: {succeeded} succeeded, {failed} failed, {skipped + mismatch} skipped"
        )

        for package_id, status in self._last_results.items():
            row = self.model.row_for_id(package_id)
            if row < 0:
                continue
            if action == "uninstall" and status == "success":
                self.model.beginRemoveRows(QtCore.QModelIndex(), row, row)
                self.model.rows.pop(row)
                self.model.endRemoveRows()
            else:
                self.model.rows[row]["last_status"] = status
                index = self.model.index(row, 0)
                self.model.dataChanged.emit(
                    index,
                    self.model.index(row, self.model.columnCount() - 1),
                    [
                        QtCore.Qt.ItemDataRole.DisplayRole,
                        QtCore.Qt.ItemDataRole.ForegroundRole,
                        QtCore.Qt.ItemDataRole.ToolTipRole,
                    ],
                )
        self._update_selection_count()
        # Automatically refresh package list after operation finishes
        QtCore.QTimer.singleShot(1200, self.load_packages)

    def show_info(self):
        ids = self.checked_ids() or self.selected_ids()
        if len(ids) != 1 or self._worker_running(self._info_worker):
            return
        self._fetch_and_show_info(ids[0])

    def _cancel_all(self):
        self.logger.info("Cancel requested for workers=%s", [type(worker).__name__ for worker in self._workers])
        for worker in list(self._workers):
            worker.cancel()
        self.status.setText("Operation cancelled by user")

    def set_theme(self, theme):
        self.logger.info("Theme changed: %s", theme)
        self.current_theme = theme
        self.settings.setValue("theme", theme)
        apply_theme(QtWidgets.QApplication.instance(), theme)
        self.model.layoutChanged.emit()

    def _toggle_show_console(self, checked):
        self.show_console = bool(checked)
        self.settings.setValue("show_console", self.show_console)
        self.logger.info("Terminal window visibility set to: %s", self.show_console)

    def _warn(self, message):
        self.logger.warning(message)
        QtWidgets.QMessageBox.warning(self, "Winget GUI", message)

    def about(self):
        QtWidgets.QMessageBox.about(
            self,
            "About Winget Package Manager",
            f"<b>Winget Package Manager</b><br>Version {APP_VERSION}<br><br>A modern, high-performance GUI frontend for Windows Package Manager (winget).",
        )
