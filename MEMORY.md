# 🧠 MEMORY.md — Repository Memory & Architecture Decisions

This document preserves the architectural map, component boundaries, key design decisions, and operational invariants for `winget-upgrade`.

---

## 🏛️ System Architecture & Component Roles

```mermaid
graph TD
    User([User Interaction]) --> MainWindow[MainWindow (PyQt6)]
    MainWindow --> ThemeEngine[Theme Engine (theme.py)]
    MainWindow --> PackageModel[PackageModel (QAbstractTableModel)]
    MainWindow --> ConfigManager[ConfigManager (config.py)]
    MainWindow --> Workers[Background Workers (workers.py)]
    
    Workers -->|Async QThread| WingetBackend[WingetBackend (winget.py)]
    WingetBackend -->|Subprocess CLI| WingetCLI[winget.exe]
    
    Workers -->|Signals: progress, package_started, package_result| MainWindow
    Workers -->|Logging Stream| QtLogHandler[QtLogHandler (HTML formatted)]
    QtLogHandler --> LogDock[Activity Terminal (Fira Code)]
```

---

## 🧩 Component Directory & Contracts

### 1. `winget_gui/ui/theme.py`
- **Purpose**: Provides complete QSS stylesheets and `QPalette` settings for Dark, Light, and System modes.
- **Key Functions**:
  - `get_system_theme()`: Reads Windows registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme`.
  - `resolve_theme_mode(mode)`: Resolves `"System"` to `"Dark"` or `"Light"`.
  - `get_status_color(status_key, mode)`: Returns high-contrast `QColor` tokens for status states (`success`, `failed`, `in_progress`, `skipped`, `mismatch`, `available`, `excluded`, `default`).
  - `stylesheet(mode)`: Returns rich QSS with styled buttons, tables, scrollbars, dialogs, and text edits with Fira Code.

### 2. `winget_gui/ui/main_window.py`
- **Purpose**: Main desktop window, table view, toolbar actions, context menu, and terminal log dock.
- **Key Components**:
  - `PackageModel`: 6-column `QAbstractTableModel` (`["", "Package Name", "Package ID", "Installed", "Available", "Status"]`). Handles `CheckStateRole`, `DisplayRole`, `ForegroundRole`, `FontRole`, and `ToolTipRole`.
  - `QtLogHandler`: Formats logging records into rich HTML with timestamps (`HH:MM:SS.mmm`), colored level tags (Green `[INFO]`, Yellow `[WARN]`, Red `[ERROR]`), module tags, and traceback formatting.
  - `_operation_done`: Handles post-operation model updates, status bar summary, and auto-refreshes package list via `QTimer.singleShot(1200, self.load_packages)`.

### 3. `winget_gui/workers.py`
- **Purpose**: Asynchronous worker threads inheriting from `QtCore.QThread` and `CancelMixin`.
- **Workers**:
  - `PackageWorker`: Queries winget catalog and emits `packages_ready(list)` or `error(str)`.
  - `OperationWorker`: Executes batch package operations (`upgrade`, `force_reinstall`, `uninstall`, `powershell`). Emits `package_started(package_id, label)`, `progress_step`, `progress_count`, `package_result`, and `finished_all`.
  - `InfoWorker`: Queries package details (`winget show`) and emits `result_ready(package_id, output)`.

### 4. `winget_gui/winget.py`
- **Purpose**: Subprocess wrapper managing `winget.exe` execution.
- **Quirks & Logic**:
  - Auto-discovers executable in `PATH` or `%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe`.
  - Maps winget exit codes (`0x8A15002B`, `0x881A001F`, `0x881A002B` -> `no_applicable_upgrade`; `0x8A15003B`, `0x881A008E` -> `installer_technology_mismatch`).
  - Implements cancellation checking and timeouts.

### 5. `winget_gui/config.py`
- **Purpose**: Configuration persistence for exclusions (`excluded_ids`, `excluded_patterns`, `exclude_unknown_versions`).
- **Safety**: Atomic write to temporary file with `os.replace`; automatic `.json.bak` creation on corrupt input.

### 6. `winget_gui/parser.py`
- **Purpose**: Robust dual-mode parser supporting `--output json` and localized text fallback (English & German headers, separator detection, and truncated ID handling).

---

## 🛠️ Testing & Quality Verification

- Tests located in `tests/`:
  - `tests/test_config.py`: Tests atomic saving, corrupt file backups, and validation.
  - `tests/test_parser.py`: Tests English/German output parsing and malformed output handling.
  - `tests/test_winget.py`: Tests winget code maps, wildcard exclusions, `OperationWorker` progress/started signals, `PackageModel` columns and roles, and theme stylesheets/colors.
- Command: `uv run pytest` (All 11 tests pass in ~0.06s).
