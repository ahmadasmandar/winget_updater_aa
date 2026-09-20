import ctypes
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets

# --- Configuration ---

DEFAULT_CONFIG = {
    "excluded_patterns": ["adobe", "camtasia", "antigravity"],
    "excluded_ids": [
        "Microsoft.VisualStudio.2022.BuildTools",
        "Microsoft.DotNet.Framework.DeveloperPack",
    ],
    "exclude_unknown_versions": True,
}


def load_config(base_dir):
    """Load config from config.json, creating default if missing."""
    config_path = os.path.join(base_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    # Write default config
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()


def get_base_dir():
    """Get base directory (handles frozen/dev mode)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# --- Workers ---


class WingetWorker(QtCore.QThread):
    """Background worker for winget package enumeration"""

    finished = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("Loading packages...")
            packages = self._get_packages()
            self.finished.emit(packages)
        except Exception as e:
            self.error.emit(str(e))

    def _get_packages(self):
        # Accept source agreements first
        subprocess.run(
            ["winget", "list", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Parse winget upgrade text output
        self.progress.emit("Querying upgradable packages...")
        return self._fetch_upgrade_list()

    def _fetch_upgrade_list(self):
        """Fetch and parse winget upgrade output."""
        try:
            result = subprocess.run(
                [
                    "winget",
                    "upgrade",
                    "--include-unknown",
                    "--accept-source-agreements",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return self._parse_text_output(result.stdout)
        except Exception:
            return []

    def _parse_text_output(self, output):
        """Parse winget text output into package list with robust ID handling"""
        packages = []
        lines = output.splitlines()

        # Find separator line (line with many dashes like "--------------------")
        separator_idx = -1
        for i, line in enumerate(lines):
            # Normalize Unicode box-drawing dashes to regular dashes
            normalized = line.replace("─", "-")
            # Check if line is mostly dashes (at least 20 dash characters)
            dash_count = normalized.count("-")
            if dash_count >= 20:
                separator_idx = i
                break

        if separator_idx < 1 or separator_idx + 1 >= len(lines):
            return packages

        # Get header and separator to determine column positions
        header = lines[separator_idx - 1]

        # Find column positions by explicit header names (supports EN/DE)
        col_map = {}
        for keyword, col_name in [
            ("Name", "Name"),
            ("Id", "Id"),
            ("ID", "Id"),
            ("Version", "Version"),
            ("Available", "Available"),
            ("Verfügbar", "Available"),
            ("Source", "Source"),
            ("Quelle", "Source"),
        ]:
            pos = header.find(keyword)
            if pos >= 0 and col_name not in col_map:
                col_map[col_name] = pos

        # We need at least Name, Id, Version columns
        required = ["Name", "Id", "Version"]
        if not all(k in col_map for k in required):
            return packages

        # Build ordered column list with positions
        col_order = ["Name", "Id", "Version", "Available", "Source"]
        col_positions = []
        for col in col_order:
            if col in col_map:
                col_positions.append((col, col_map[col]))

        # Sort by position
        col_positions.sort(key=lambda x: x[1])

        # Get column start positions
        positions = [p[1] for p in col_positions]

        # Parse data lines
        for line in lines[separator_idx + 1 :]:
            if not line.strip():
                continue
            # Skip summary lines (e.g., "36 Aktualisierungen verfügbar", "10 upgrades available")
            lower_line = line.lower()
            if ("aktualisierung" in lower_line or "upgrade" in lower_line) and "winget" not in lower_line:
                if len(line.split()) <= 5:
                    continue

            # Extract columns with special handling for ID column
            row_data = {}
            for idx, (col_name, col_start) in enumerate(col_positions):

                # Special handling for ID column - extract complete token without truncation
                if col_name == "Id":
                    # Strategy: Extract the complete ID by looking at a wider region
                    # Account for column misalignment by searching backwards and forwards

                    # Start searching a bit before the detected column position
                    # to account for misalignment
                    search_start = max(0, col_start - 5)

                    # Find the end boundary (Version column start or line end)
                    if idx + 1 < len(positions):
                        # Extend search to ensure we capture the full ID
                        search_end = positions[idx + 1] + 20
                    else:
                        search_end = len(line)

                    # Extract the wider region that should contain the ID
                    id_region = line[search_start:search_end] if search_start < len(line) else ""

                    # Split by whitespace and find tokens
                    tokens = id_region.split()

                    # Find the token that looks most like a package ID
                    # Package IDs have dots and are alphanumeric (e.g., Microsoft.VisualStudio.2022.BuildTools)
                    val = ""
                    best_token = ""
                    max_dots = 0

                    for token in tokens:
                        # Remove trailing punctuation/ellipsis
                        clean_token = token.rstrip("…").rstrip(".")

                        # Skip if empty or looks like a version number (e.g., 1.2.3 or v1.2.3)
                        if not clean_token or re.match(r"^[vV]?\d+\.\d+", clean_token):
                            continue

                        # Count dots - package IDs typically have multiple dots
                        dot_count = clean_token.count(".")

                        # Check if it's a valid package ID format (allow +, letters, numbers, dots, dashes, underscores)
                        if re.match(r"^[a-zA-Z0-9._+-]+$", clean_token):
                            # Prefer tokens with more dots (more likely to be complete IDs)
                            if dot_count > max_dots or (dot_count == max_dots and len(clean_token) > len(best_token)):
                                best_token = clean_token
                                max_dots = dot_count

                    val = best_token if best_token else ""

                else:
                    # Standard column extraction for other columns
                    # Find the end position (start of next column or end of line)
                    if idx + 1 < len(positions):
                        col_end = positions[idx + 1]
                        val = line[col_start:col_end].strip() if col_start < len(line) else ""
                    else:
                        # Last column extends to end of line
                        val = line[col_start:].strip() if col_start < len(line) else ""

                row_data[col_name] = val

            # Validate package data before adding
            pkg_id = row_data.get("Id", "")
            pkg_name = row_data.get("Name", "")

            # Skip if ID or Name is missing
            if not pkg_id or not pkg_name:
                continue

            # Skip if ID contains truncation markers or is suspiciously short
            if "…" in pkg_id or len(pkg_id) < 3:
                self.progress.emit(f"Skipping truncated/invalid ID: {pkg_id}")
                continue

            # Skip if ID contains only special characters (malformed)
            if not re.match(r"^[a-zA-Z0-9._-]+$", pkg_id):
                self.progress.emit(f"Skipping malformed ID: {pkg_id}")
                continue

            packages.append(
                {
                    "Name": pkg_name,
                    "Id": pkg_id,
                    "Version": row_data.get("Version", ""),
                    "AvailableVersion": row_data.get("Available", ""),
                    "Source": row_data.get("Source", ""),
                }
            )

        return packages


class OperationWorker(QtCore.QThread):
    """Background worker for upgrade/uninstall operations — keeps UI responsive."""

    progress = QtCore.pyqtSignal(str)
    progress_count = QtCore.pyqtSignal(int, int)  # completed, total
    progress_detail = QtCore.pyqtSignal(int, int, int)  # index (1-based), total, percent
    package_result = QtCore.pyqtSignal(str, str, str)  # pkg_id, status ('success' | 'failed' | 'skipped' | 'mismatch'), output
    finished_all = QtCore.pyqtSignal(int, int, int, int)  # success, fail, skipped, mismatch

    def __init__(self, operations, logger, parent=None):
        """
        operations: list of (cmd_list, pkg_id, action_name, pkg_name, pkg_source) tuples.
        Each operation is run sequentially in the background thread.
        """
        super().__init__(parent)
        self.operations = operations
        self.logger = logger
        self.parent = parent
        self._cancelled = False
        self._process = None

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception as e:
                self.logger.error(f"Error terminating process: {e}")

    def run(self):
        success = 0
        failed = 0
        skipped = 0
        mismatch = 0
        total = len(self.operations)

        self.progress_count.emit(0, total)

        for i, (cmd, pkg_id, action_name, pkg_name, pkg_source) in enumerate(self.operations, 1):
            if self._cancelled:
                break

            self.progress.emit(f"{action_name} {pkg_id} ({i}/{total})...")
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
            print(f"\n> {cmd_str}", flush=True)
            self.logger.info(f"Processing: {pkg_id} [{action_name}]")
            self.logger.info(f"Package details - Name: {pkg_name}, ID: {pkg_id}, Source: {pkg_source}")

            # Verify package exists before upgrade/reinstall
            if action_name in ("Upgrade", "Force Reinstall"):
                verify = subprocess.run(
                    [
                        "winget",
                        "list",
                        "--id",
                        pkg_id,
                        "--accept-source-agreements",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                not_found = "No installed package found" in verify.stdout or "kein installiertes Paket" in verify.stdout
                if not_found:
                    self.logger.warning(f"Package {pkg_id} not found in installed list, skipping")
                    self.package_result.emit(pkg_id, "failed", "Not found in installed packages")
                    failed += 1
                    self.progress_count.emit(success + failed + skipped + mismatch, total)
                    continue

            try:
                # Run subprocess directly connected to the terminal for "Normal Output"
                # This allows winget to detect the TTY and use its native interactive visuals.
                self._process = subprocess.Popen(
                    cmd,
                    stdout=None,
                    stderr=None,
                    bufsize=0,
                )
                self._process.wait()

                # 2316632107 (0x881A002B) is WINGET_CL_NO_APPLICABLE_UPGRADE
                # 2316632095 (0x881A001F) is WINGET_CL_UPDATE_NOT_APPLICABLE
                # -2011627477 and -2011627489 are their signed counterparts
                # 2316632206 (0x881A008E) is WINGET_CL_INSTALLER_TECHNOLOGY_MISMATCH
                no_upgrade_codes = (2316632107, 2316632095, -2011627477, -2011627489)
                mismatch_codes = (2316632206, -2011627378)

                if self._process.returncode == 0:
                    self.logger.info(f"Success: {pkg_id}")
                    self.package_result.emit(pkg_id, "success", "")
                    success += 1
                elif self._process.returncode in no_upgrade_codes:
                    self.logger.warning(f"No applicable upgrade found for {pkg_id} (code {self._process.returncode})")
                    self.package_result.emit(pkg_id, "skipped", "No applicable upgrade found")
                    skipped += 1
                elif self._process.returncode in mismatch_codes:
                    self.logger.error(f"Failed due to installer technology mismatch: {pkg_id} (code {self._process.returncode})")
                    self.package_result.emit(pkg_id, "mismatch", "Installer technology mismatch")
                    mismatch += 1
                else:
                    self.logger.error(f"Failed: {pkg_id} (code {self._process.returncode})")
                    self.package_result.emit(pkg_id, "failed", f"Error code: {self._process.returncode}")
                    failed += 1
            except Exception as e:
                self.logger.error(f"Exception processing {pkg_id}: {e}")
                self.package_result.emit(pkg_id, "failed", str(e))
                failed += 1
            finally:
                self._process = None

            self.progress_count.emit(success + failed + skipped + mismatch, total)

        self.finished_all.emit(success, failed, skipped, mismatch)

    @staticmethod
    def _extract_ratio_percent(text: str) -> int | None:
        match = re.search(
            r"([0-9.,]+)\s*(KB|MB|GB)\s*/\s*([0-9.,]+)\s*(KB|MB|GB)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None

        current_val = OperationWorker._to_bytes(match.group(1), match.group(2))
        total_val = OperationWorker._to_bytes(match.group(3), match.group(4))
        if total_val <= 0:
            return None

        percent = int(min(100, max(0, round((current_val / total_val) * 100))))
        return percent

    @staticmethod
    def _to_bytes(value: str, unit: str) -> float:
        units = {
            "kb": 1024,
            "mb": 1024**2,
            "gb": 1024**3,
        }
        unit_key = unit.lower()
        factor = units.get(unit_key, 1)
        normalized = value.replace(",", ".")
        try:
            return float(normalized) * factor
        except ValueError:
            return 0.0


# --- Exclusion Manager Dialog ---


class ExclusionManagerDialog(QtWidgets.QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Manage Exclusions")
        self.resize(550, 450)
        self.setStyleSheet(parent.styleSheet() if parent else "")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tab widget to switch between Excluded IDs and Excluded Patterns
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: Excluded IDs
        self.ids_tab = QtWidgets.QWidget()
        self.ids_layout = QtWidgets.QVBoxLayout(self.ids_tab)
        self.ids_layout.setContentsMargins(8, 8, 8, 8)
        self.ids_list = QtWidgets.QListWidget()
        for item in self.config.get("excluded_ids", []):
            self.ids_list.addItem(item)
        self.ids_layout.addWidget(self.ids_list)

        self.ids_btn_layout = QtWidgets.QHBoxLayout()
        self.add_id_btn = QtWidgets.QPushButton("Add ID")
        self.remove_id_btn = QtWidgets.QPushButton("Remove Selected")
        self.ids_btn_layout.addWidget(self.add_id_btn)
        self.ids_btn_layout.addWidget(self.remove_id_btn)
        self.ids_layout.addLayout(self.ids_btn_layout)
        self.tabs.addTab(self.ids_tab, "🚫 Excluded IDs")

        # Tab 2: Excluded Patterns
        self.patterns_tab = QtWidgets.QWidget()
        self.patterns_layout = QtWidgets.QVBoxLayout(self.patterns_tab)
        self.patterns_layout.setContentsMargins(8, 8, 8, 8)
        self.patterns_list = QtWidgets.QListWidget()
        for item in self.config.get("excluded_patterns", []):
            self.patterns_list.addItem(item)
        self.patterns_layout.addWidget(self.patterns_list)

        self.patterns_btn_layout = QtWidgets.QHBoxLayout()
        self.add_pattern_btn = QtWidgets.QPushButton("Add Pattern")
        self.remove_pattern_btn = QtWidgets.QPushButton("Remove Selected")
        self.patterns_btn_layout.addWidget(self.add_pattern_btn)
        self.patterns_btn_layout.addWidget(self.remove_pattern_btn)
        self.patterns_layout.addLayout(self.patterns_btn_layout)
        self.tabs.addTab(self.patterns_tab, "🔍 Excluded Patterns")

        # Dialog Buttons
        dialog_buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

        # Wire up Add/Remove buttons
        self.add_id_btn.clicked.connect(self.add_id)
        self.remove_id_btn.clicked.connect(self.remove_id)
        self.add_pattern_btn.clicked.connect(self.add_pattern)
        self.remove_pattern_btn.clicked.connect(self.remove_pattern)

    def add_id(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Add Excluded ID", "Enter Package ID to exclude:")
        if ok and text.strip():
            val = text.strip()
            # Check if duplicate
            if not self.ids_list.findItems(val, QtCore.Qt.MatchFlag.MatchExactly):
                self.ids_list.addItem(val)

    def remove_id(self):
        for item in self.ids_list.selectedItems():
            self.ids_list.takeItem(self.ids_list.row(item))

    def add_pattern(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Add Excluded Pattern", "Enter Name Pattern to exclude (case-insensitive):")
        if ok and text.strip():
            val = text.strip().lower()
            if not self.patterns_list.findItems(val, QtCore.Qt.MatchFlag.MatchExactly):
                self.patterns_list.addItem(val)

    def remove_pattern(self):
        for item in self.patterns_list.selectedItems():
            self.patterns_list.takeItem(self.patterns_list.row(item))

    def get_exclusions(self):
        ids = [self.ids_list.item(i).text() for i in range(self.ids_list.count())]
        patterns = [self.patterns_list.item(i).text() for i in range(self.patterns_list.count())]
        return ids, patterns


# --- Main Window ---


class WingetManager(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Winget Package Manager")
        self.resize(1400, 700)
        self.setStyleSheet(self._dark_theme())

        # Set window icon
        icon_path = self._get_resource_path("updated.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self._base_dir = get_base_dir()
        self.config = load_config(self._base_dir)
        self.worker = None
        self.op_worker = None
        self.failed_ids = set()
        self.skipped_ids = set()
        self.mismatch_ids = set()

        self._setup_logging()
        self._setup_ui()
        self._connect_signals()
        self.load_packages()

    def _get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def _setup_logging(self):
        """Setup logging to file with timestamp"""
        self.log_dir = os.path.join(self._base_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(self.log_dir, f"winget_log_{timestamp}.txt")

        # Use a named logger to avoid stacking handlers via basicConfig
        self.logger = logging.getLogger("winget_manager")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            self.logger.addHandler(logging.FileHandler(log_file, encoding="utf-8"))
            self.logger.addHandler(logging.StreamHandler(sys.stdout))
            for h in self.logger.handlers:
                h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        self.logger.info("Winget Manager started")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info(f"Config: {self.config}")

    def _setup_ui(self):
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)

        # Search bar
        search_layout = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter packages...")
        self.search_input.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_input)

        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.setFixedWidth(100)
        self.deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        self.deselect_all_btn.setFixedWidth(100)
        search_layout.addWidget(self.select_all_btn)
        search_layout.addWidget(self.deselect_all_btn)
        self.layout.addLayout(search_layout)

        # Table Widget with checkbox column
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["✓", "Name", "ID", "Current", "Available", "Source"])
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        self.table.setColumnWidth(0, 40)  # Checkbox column
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)  # Name stretches
        self.table.setColumnWidth(2, 380)  # ID (increased for long package names)
        self.table.setColumnWidth(3, 140)  # Current
        self.table.setColumnWidth(4, 140)  # Available
        self.table.setColumnWidth(5, 120)  # Source
        self.layout.addWidget(self.table)

        # Progress bar (hidden by default)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)

        self.upgrade_btn = QtWidgets.QPushButton("⬆ Upgrade Selected")
        self.force_reinstall_btn = QtWidgets.QPushButton("⚡ Force Reinstall")
        self.upgrade_all_btn = QtWidgets.QPushButton("⬆⬆ Upgrade All")
        self.uninstall_btn = QtWidgets.QPushButton("🗑 Uninstall")
        self.exclude_btn = QtWidgets.QPushButton("🚫 Exclude")
        self.manage_excludes_btn = QtWidgets.QPushButton("⚙ Excludes")
        self.info_btn = QtWidgets.QPushButton("ℹ Info")
        self.open_logs_btn = QtWidgets.QPushButton("📂 Logs")
        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        self.upgrade_powershell_btn = QtWidgets.QPushButton("💻 Upgrade PowerShell")

        self.upgrade_all_btn.setStyleSheet("background-color: #9ece6a;")
        self.force_reinstall_btn.setStyleSheet("background-color: #ff9e64; color: #1a1b26;")
        self.uninstall_btn.setStyleSheet("background-color: #f7768e;")
        self.exclude_btn.setStyleSheet("background-color: #bb9af7; color: #1a1b26;")
        self.manage_excludes_btn.setStyleSheet("background-color: #bb9af7; color: #1a1b26;")
        self.open_logs_btn.setStyleSheet("background-color: #414868; color: #c0caf5;")
        self.upgrade_powershell_btn.setStyleSheet("background-color: #7dcfff; color: #1a1b26;")

        for btn in (
            self.upgrade_btn,
            self.force_reinstall_btn,
            self.upgrade_all_btn,
            self.uninstall_btn,
            self.exclude_btn,
            self.manage_excludes_btn,
            self.info_btn,
            self.open_logs_btn,
            self.refresh_btn,
            self.upgrade_powershell_btn,
        ):
            btn_layout.addWidget(btn)

        self.layout.addLayout(btn_layout)

        # Status bar with package count
        status_layout = QtWidgets.QHBoxLayout()
        self.status = QtWidgets.QLabel("Ready.")
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(self.status)
        status_layout.addWidget(self.count_label)
        self.layout.addLayout(status_layout)

    def _connect_signals(self):
        self.refresh_btn.clicked.connect(self.load_packages)
        self.upgrade_btn.clicked.connect(self.upgrade_selected)
        self.force_reinstall_btn.clicked.connect(self.force_reinstall_selected)
        self.upgrade_all_btn.clicked.connect(self.upgrade_all)
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        self.exclude_btn.clicked.connect(self.exclude_selected)
        self.manage_excludes_btn.clicked.connect(self.show_exclusion_manager)
        self.info_btn.clicked.connect(self.show_info_selected)
        self.open_logs_btn.clicked.connect(self.open_logs_folder)
        self.upgrade_powershell_btn.clicked.connect(self.upgrade_powershell)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.search_input.textChanged.connect(self.filter_table)
        self.select_all_btn.clicked.connect(self.check_all)
        self.deselect_all_btn.clicked.connect(self.uncheck_all)
        self.table.doubleClicked.connect(self.show_info_selected)
        self.table.cellClicked.connect(self._on_cell_clicked)

    def _dark_theme(self):
        return """
        QWidget {
            background-color: #1a1b26;
            color: #c0caf5;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }
        QMainWindow { background-color: #1a1b26; }
        QHeaderView::section {
            background-color: #24283b;
            color: #7aa2f7;
            padding: 10px 8px;
            border: none;
            font-weight: bold;
            border-bottom: 2px solid #7aa2f7;
        }
        QTableWidget {
            gridline-color: transparent;
            border: 1px solid #292e42;
            border-radius: 8px;
            selection-background-color: #364a82;
            selection-color: #ffffff;
            alternate-background-color: #1f2335;
        }
        QTableWidget::item {
            padding: 8px 6px;
            border-bottom: 1px solid #292e42;
        }
        QTableWidget::item:selected {
            background-color: #364a82;
        }
        QTableWidget::item:hover:!selected {
            background-color: #2a3450;
        }
        QPushButton {
            background-color: #7aa2f7;
            border: none;
            border-radius: 6px;
            padding: 10px 18px;
            color: #1a1b26;
            font-weight: 600;
            min-height: 22px;
        }
        QPushButton:hover {
            background-color: #89b4fa;
        }
        QPushButton:pressed {
            background-color: #6a92e7;
        }
        QPushButton:disabled {
            background-color: #414868;
            color: #565f89;
        }
        QLineEdit {
            background-color: #24283b;
            border: 2px solid #414868;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 14px;
            selection-background-color: #7aa2f7;
        }
        QLineEdit:focus {
            border-color: #7aa2f7;
        }
        QProgressBar {
            border: none;
            border-radius: 6px;
            background-color: #24283b;
            max-height: 12px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #7aa2f7;
            border-radius: 6px;
        }
        QMenu {
            background-color: #24283b;
            color: #c0caf5;
            border: 1px solid #414868;
            border-radius: 8px;
            padding: 6px;
        }
        QMenu::item {
            padding: 8px 24px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #364a82;
        }
        QScrollBar:vertical {
            border: none;
            background-color: transparent;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #414868;
            border-radius: 6px;
            min-height: 30px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #7aa2f7;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QLabel {
            color: #a9b1d6;
        }
        QToolTip {
            background-color: #24283b;
            color: #c0caf5;
            border: 1px solid #7aa2f7;
            border-radius: 4px;
            padding: 6px;
        }
        QMessageBox {
            background-color: #1a1b26;
        }
        QMessageBox QLabel {
            color: #c0caf5;
        }
        QMessageBox QPushButton {
            min-width: 80px;
        }
        QTabWidget::pane {
            border: 1px solid #414868;
            border-radius: 8px;
            background-color: #1a1b26;
            top: -1px;
        }
        QTabBar::tab {
            background-color: #24283b;
            color: #7aa2f7;
            border: 1px solid #414868;
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: 8px 16px;
            margin-right: 4px;
        }
        QTabBar::tab:selected {
            background-color: #1a1b26;
            color: #c0caf5;
            border-bottom: 1px solid #1a1b26;
            font-weight: bold;
        }
        QTabBar::tab:hover:!selected {
            background-color: #2a3450;
        }
        QListWidget {
            background-color: #24283b;
            border: 1px solid #414868;
            border-radius: 8px;
            padding: 6px;
            color: #c0caf5;
        }
        QListWidget::item {
            padding: 8px;
            border-radius: 4px;
        }
        QListWidget::item:selected {
            background-color: #364a82;
            color: #ffffff;
        }
        QListWidget::item:hover:!selected {
            background-color: #2a3450;
        }
        """

    # --- Package loading ---

    def load_packages(self):
        if self.op_worker and self.op_worker.isRunning():
            return  # Don't reload while an operation is running
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self._set_loading(True)
        self.table.setRowCount(0)

        self.worker = WingetWorker()
        self.worker.finished.connect(self._on_packages_loaded)
        self.worker.error.connect(self._on_load_error)
        self.worker.progress.connect(lambda msg: self.status.setText(msg))
        self.worker.start()

    def _should_exclude(self, pkg):
        """Check if a package should be excluded based on config rules."""
        pkg_id_orig = pkg.get("Id", "")
        if pkg_id_orig in getattr(self, "skipped_ids", set()):
            return True

        ver = pkg.get("Version", "").lower()
        if self.config.get("exclude_unknown_versions", True) and ("unknown" in ver or ver == "unknown"):
            return True

        pkg_id = pkg_id_orig.lower()
        pkg_name = pkg.get("Name", "").lower()

        for pattern in self.config.get("excluded_patterns", []):
            p = pattern.lower()
            if p in pkg_id or p in pkg_name:
                return True

        for exc_id in self.config.get("excluded_ids", []):
            if exc_id.lower() in pkg_id:
                return True

        return False

    def _on_packages_loaded(self, packages):
        self._set_loading(False)
        self.table.setSortingEnabled(False)

        filtered_packages = [pkg for pkg in packages if not self._should_exclude(pkg)]

        self.logger.info(f"Loaded {len(filtered_packages)} packages")

        for pkg in filtered_packages:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox column
            chk_item = QtWidgets.QTableWidgetItem()
            chk_item.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk_item)

            # Data columns (shifted by 1)
            pkg_id = pkg.get("Id", "")

            # Check for failure / skip / technology mismatch history
            is_failed = pkg_id in self.failed_ids
            is_skipped = pkg_id in self.skipped_ids
            is_mismatch = pkg_id in self.mismatch_ids

            if is_failed:
                bg_color = QtGui.QColor("#3d2e2e")  # Red
                tooltip_suffix = " (Last action failed)"
            elif is_skipped:
                bg_color = QtGui.QColor("#3d352e")  # Yellow/Orange
                tooltip_suffix = " (No applicable upgrade)"
            elif is_mismatch:
                bg_color = QtGui.QColor("#3d254c")  # Dark purple
                tooltip_suffix = " (Installer technology mismatch. Needs manual Uninstall & Reinstall)"
            else:
                bg_color = None
                tooltip_suffix = ""

            for col, key in enumerate(["Name", "Id", "Version", "AvailableVersion", "Source"]):
                val = pkg.get(key, "")
                item = QtWidgets.QTableWidgetItem(val)
                item.setToolTip(val + tooltip_suffix if tooltip_suffix else val)
                if bg_color:
                    item.setBackground(bg_color)
                self.table.setItem(row, col + 1, item)

        self.table.setSortingEnabled(True)
        self._update_count()
        self.status.setText("Ready.")

    def _on_load_error(self, error):
        self._set_loading(False)
        self.status.setText(f"Error: {error}")
        self.logger.error(f"Error loading packages: {error}")

    def _set_loading(self, loading):
        self.progress_bar.setVisible(loading)
        for btn in (
            self.upgrade_btn,
            self.force_reinstall_btn,
            self.upgrade_all_btn,
            self.uninstall_btn,
            self.exclude_btn,
            self.manage_excludes_btn,
            self.info_btn,
            self.open_logs_btn,
            self.refresh_btn,
        ):
            btn.setEnabled(not loading)

    def _update_count(self):
        visible = sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))
        total = self.table.rowCount()
        self.count_label.setText(f"{visible} of {total} packages")

    def filter_table(self, text):
        text = text.lower()
        self.table.setUpdatesEnabled(False)
        for row in range(self.table.rowCount()):
            match = False
            for col in range(1, self.table.columnCount()):  # Skip checkbox column
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)
        self.table.setUpdatesEnabled(True)
        self._update_count()

    def _on_cell_clicked(self, row, col):
        """Toggle checkbox when row is clicked"""
        if col == 0:
            return  # Let normal checkbox handling work
        chk_item = self.table.item(row, 0)
        if chk_item:
            new_state = QtCore.Qt.CheckState.Unchecked if chk_item.checkState() == QtCore.Qt.CheckState.Checked else QtCore.Qt.CheckState.Checked
            chk_item.setCheckState(new_state)

    def check_all(self):
        """Check all visible packages"""
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                chk_item = self.table.item(row, 0)
                if chk_item and chk_item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable:
                    chk_item.setCheckState(QtCore.Qt.CheckState.Checked)

    def uncheck_all(self):
        """Uncheck all packages"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def get_checked_ids(self):
        """Get IDs of all checked packages"""
        ids = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == QtCore.Qt.CheckState.Checked:
                id_item = self.table.item(row, 2)  # ID is now column 2
                if id_item:
                    ids.append(id_item.text())
        return ids

    def get_selected_ids(self):
        """Get IDs from checked packages (preferred) or selected rows"""
        checked = self.get_checked_ids()
        if checked:
            return checked
        # Fallback to selection
        rows = set(item.row() for item in self.table.selectedItems())
        return [self.table.item(row, 2).text() for row in rows if self.table.item(row, 2)]

    # --- Operations (non-blocking via OperationWorker) ---

    def _validate_ids(self, ids):
        """Filter out invalid package IDs and return valid ones."""
        valid = []
        for pkg_id in ids:
            if not pkg_id or len(pkg_id) < 3:
                self.logger.warning(f"Skipping invalid ID (too short): '{pkg_id}'")
                continue
            if "…" in pkg_id or "..." in pkg_id:
                self.logger.warning(f"Skipping truncated ID: '{pkg_id}'")
                continue
            if not re.match(r"^[a-zA-Z0-9._+-]+$", pkg_id):
                self.logger.warning(f"Skipping malformed ID: '{pkg_id}'")
                continue
            valid.append(pkg_id)

        if len(valid) < len(ids):
            self.logger.warning(f"Skipped {len(ids) - len(valid)} invalid ID(s)")
        return valid

    def upgrade_selected(self):
        ids = self.get_selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "No package selected.")
            return
        self._run_operation(ids, "upgrade")

    def upgrade_all(self):
        ids = [self.table.item(row, 2).text() for row in range(self.table.rowCount()) if self.table.item(row, 2) and not self.table.isRowHidden(row)]
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "No upgradable packages found.")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", f"Upgrade all {len(ids)} visible packages?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._run_operation(ids, "upgrade")

    def force_reinstall_selected(self):
        ids = self.get_selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "No package selected.")
            return

        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm Force Reinstall",
                "This will force a reinstall of the selected packages. "
                "Use this if standard upgrade fails "
                "(e.g., 'No applicable upgrade found').\n\nContinue?",
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return

        self._run_operation(ids, "force_reinstall")

    def uninstall_selected(self):
        ids = self.get_selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "No package selected.")
            return

        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm Uninstall",
                f"Uninstall {len(ids)} package(s)?\n\n" + "\n".join(ids[:10]) + ("..." if len(ids) > 10 else ""),
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return

        self._run_operation(ids, "uninstall")

    def exclude_selected(self):
        ids = self.get_selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "No package selected.")
            return

        valid_ids = self._validate_ids(ids)
        if not valid_ids:
            QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "No valid package IDs to exclude.",
            )
            return

        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm Exclude",
                f"Exclude {len(valid_ids)} package(s) from future lists?\n\n" + "\n".join(valid_ids[:10]) + ("..." if len(valid_ids) > 10 else ""),
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return

        for pkg_id in valid_ids:
            if pkg_id not in self.config["excluded_ids"]:
                self.config["excluded_ids"].append(pkg_id)

        self.save_config()
        self.load_packages()

    def save_config(self):
        config_path = os.path.join(self._base_dir, "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

    def _run_operation(self, ids, action):
        """Build operation list and launch OperationWorker."""
        valid_ids = self._validate_ids(ids)
        if not valid_ids:
            QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "No valid package IDs to process. All IDs were invalid or truncated.",
            )
            return

        operations = []
        for pkg_id in valid_ids:
            self.failed_ids.discard(pkg_id)
            self.skipped_ids.discard(pkg_id)
            self.mismatch_ids.discard(pkg_id)

            # Find name and source from the table in the main thread
            pkg_name = "unknown"
            pkg_source = "unknown"
            for row in range(self.table.rowCount()):
                id_item = self.table.item(row, 2)
                if id_item and id_item.text() == pkg_id:
                    name_item = self.table.item(row, 1)
                    source_item = self.table.item(row, 5)
                    pkg_name = name_item.text() if name_item else "unknown"
                    pkg_source = source_item.text() if source_item else "unknown"
                    break

            if action == "upgrade":
                cmd = [
                    "winget",
                    "upgrade",
                    "--id",
                    pkg_id,
                    "-e",
                    "--include-unknown",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
                operations.append((cmd, pkg_id, "Upgrade", pkg_name, pkg_source))
            elif action == "force_reinstall":
                cmd = [
                    "winget",
                    "install",
                    "--id",
                    pkg_id,
                    "-e",
                    "--force",
                    "--include-unknown",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
                operations.append((cmd, pkg_id, "Force Reinstall", pkg_name, pkg_source))
            elif action == "uninstall":
                cmd = [
                    "winget",
                    "uninstall",
                    "--id",
                    pkg_id,
                    "-e",
                    "--accept-source-agreements",
                ]
                operations.append((cmd, pkg_id, "Uninstall", pkg_name, pkg_source))
            elif action == "uninstall_and_reinstall":
                cmd_uninstall = [
                    "winget",
                    "uninstall",
                    "--id",
                    pkg_id,
                    "-e",
                    "--accept-source-agreements",
                ]
                cmd_install = [
                    "winget",
                    "install",
                    "--id",
                    pkg_id,
                    "-e",
                    "--include-unknown",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ]
                operations.append((cmd_uninstall, pkg_id, "Uninstall (Mismatch Fix)", pkg_name, pkg_source))
                operations.append((cmd_install, pkg_id, "Install (Mismatch Fix)", pkg_name, pkg_source))
            else:
                continue

        if not operations:
            QtWidgets.QMessageBox.information(
                self,
                "Info",
                "No operations to run. All selected packages may have been skipped.",
            )
            return

        self.progress_bar.setMaximum(len(operations))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self._set_loading(True)
        self.logger.info(f"Starting {action} of {len(operations)} packages")

        self.op_worker = OperationWorker(operations, self.logger, self)
        self.op_worker.progress.connect(lambda msg: self.status.setText(msg))
        self.op_worker.progress_count.connect(self._on_operation_progress)
        self.op_worker.progress_detail.connect(self._on_operation_progress_detail)
        self.op_worker.package_result.connect(self._on_package_result)
        self.op_worker.finished_all.connect(lambda s, f, sk, m: self._on_operation_done(s, f, sk, m, action))
        self.op_worker.start()

    def _on_package_result(self, pkg_id, status, output):
        """Handle per-package result from OperationWorker."""
        if status == "failed":
            self.failed_ids.add(pkg_id)
        elif status == "skipped":
            self.skipped_ids.add(pkg_id)
        elif status == "mismatch":
            self.mismatch_ids.add(pkg_id)

    def _on_operation_done(self, success_count, fail_count, skipped_count, mismatch_count, action):
        """Handle OperationWorker completion."""
        self._set_loading(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        total = success_count + fail_count + skipped_count + mismatch_count
        msg = f"{action.replace('_', ' ').title()} complete: {success_count}/{total} succeeded."
        if skipped_count:
            msg += f"\n{skipped_count} skipped (no applicable upgrade, highlighted in yellow/orange)."
        if mismatch_count:
            msg += f"\n{mismatch_count} failed due to installer technology mismatch (highlighted in purple, needs manual uninstall & reinstall)."
        if fail_count:
            msg += f"\n{fail_count} failed (highlighted in red after refresh)."
        QtWidgets.QMessageBox.information(self, "Done", msg)
        self.load_packages()

    def _on_operation_progress(self, completed, total):
        if total <= 0:
            self.progress_bar.setMaximum(0)
            self.progress_bar.setValue(0)
            return
        self.progress_bar.setMaximum(total)
        # clamp completed to [0, total]
        clamped = max(0, min(completed, total))
        self.progress_bar.setValue(clamped)

    def _on_operation_progress_detail(self, index, total, percent):
        # Ensure base progress bar state is aligned
        self._on_operation_progress(index - 1, total)

    # --- Info dialog ---

    def show_info_selected(self):
        ids = self.get_selected_ids()
        if len(ids) != 1:
            QtWidgets.QMessageBox.information(self, "Info", "Select exactly one package.")
            return

        pkg_id = ids[0]
        self.status.setText(f"Getting info for {pkg_id}...")

        # Run info fetch in a short-lived background thread
        class InfoWorker(QtCore.QThread):
            result_ready = QtCore.pyqtSignal(str, str)  # pkg_id, output

            def __init__(self, pkg_id, parent=None):
                super().__init__(parent)
                self.pkg_id = pkg_id

            def run(self):
                result = subprocess.run(
                    ["winget", "show", "--id", self.pkg_id, "-e"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.result_ready.emit(self.pkg_id, result.stdout)

        self._info_worker = InfoWorker(pkg_id, self)
        self._info_worker.result_ready.connect(self._show_info_dialog)
        self._info_worker.start()

    def _show_info_dialog(self, pkg_id, output):
        self.status.setText("Ready.")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Package Info: {pkg_id}")
        dlg.resize(700, 500)
        dlg.setStyleSheet(self._dark_theme())

        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)

        txt = QtWidgets.QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(output)
        txt.setStyleSheet(
            """
            QTextEdit {
                background-color: #24283b;
                border: 1px solid #414868;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
        """
        )
        layout.addWidget(txt)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)

        dlg.exec()

    # --- Context menu ---

    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        ids = self.get_selected_ids()

        if ids:
            menu.addAction("⬆ Upgrade", self.upgrade_selected)
            menu.addAction("⚡ Force Reinstall", self.force_reinstall_selected)
            menu.addAction("🗑 Uninstall", self.uninstall_selected)
            # Check if any selected packages have technology mismatches
            if any(pkg_id in self.mismatch_ids for pkg_id in ids):
                menu.addAction("🗑⚡ Fix Mismatch (Uninstall & Install)", self.fix_mismatch_selected)
            menu.addAction("🚫 Exclude", self.exclude_selected)
            if len(ids) == 1:
                menu.addAction("ℹ Show Info", self.show_info_selected)
            menu.addSeparator()
            copy_action = menu.addAction("📋 Copy ID")
            copy_action.triggered.connect(lambda: QtWidgets.QApplication.clipboard().setText("\n".join(ids)))
            menu.addSeparator()

        menu.addAction("⚙ Manage Excludes...", self.show_exclusion_manager)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def fix_mismatch_selected(self):
        ids = self.get_selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Info", "No package selected.")
            return

        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm Fix Mismatch",
                "This will uninstall and then install the selected package(s) sequentially:\n\n"
                + "\n".join(ids[:10]) + ("..." if len(ids) > 10 else "")
                + "\n\nContinue?",
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return

        self._run_operation(ids, "uninstall_and_reinstall")

    def show_exclusion_manager(self):
        dlg = ExclusionManagerDialog(self.config, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            ids, patterns = dlg.get_exclusions()
            self.config["excluded_ids"] = ids
            self.config["excluded_patterns"] = patterns
            self.save_config()
            self.load_packages()

    def open_logs_folder(self):
        """Open the logs directory in Explorer"""
        if os.path.exists(self.log_dir):
            os.startfile(self.log_dir)
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Log directory does not exist yet.")

    def upgrade_powershell(self):
        """Upgrade PowerShell using winget"""
        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm PowerShell Upgrade",
                "Upgrade PowerShell to the latest version using winget?\n\n"
                "This will install the latest stable release from Microsoft.PowerShell package.",
            )
            != QtWidgets.QMessageBox.StandardButton.Yes
        ):
            return

        self._set_loading(True)
        self.status.setText("Upgrading PowerShell...")

        cmd = [
            "winget",
            "install",
            "--id",
            "Microsoft.PowerShell",
            "--source",
            "winget",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ]

        operations = [(cmd, "Microsoft.PowerShell", "Upgrade PowerShell", "PowerShell", "winget")]
        self.op_worker = OperationWorker(operations, self.logger, self)
        self.op_worker.progress.connect(lambda msg: self.status.setText(msg))
        self.op_worker.progress_count.connect(self._on_operation_progress)
        self.op_worker.package_result.connect(self._on_package_result)
        self.op_worker.finished_all.connect(lambda s, f, sk, m: self._on_operation_done(s, f, sk, m, "upgrade_powershell"))
        self.op_worker.start()


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        executable = sys.executable
        args = sys.argv[1:]
    else:
        executable = sys.executable
        args = [sys.argv[0]] + sys.argv[1:]

    params = subprocess.list2cmdline(args)
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        return int(ret) > 32
    except Exception:
        return False


if __name__ == "__main__":
    if not is_admin():
        if relaunch_as_admin():
            sys.exit(0)
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle("Fusion")
        QtWidgets.QMessageBox.warning(
            None,
            "Privilege Elevation Required",
            "This application requires Administrator privileges to perform upgrades.\n"
            "Running as a standard user may cause package installations to fail or prompt repeatedly.",
        )
    else:
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle("Fusion")

    window = WingetManager()
    window.show()
    sys.exit(app.exec())
