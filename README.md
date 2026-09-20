# 🚀 Winget Package Manager (GUI)

> A modern, high-performance desktop graphical user interface for the **Windows Package Manager (`winget`)**, built with **Python 3.14+** and **PyQt6**.

---

## ✨ Features

- **🎨 Modern Fluent Design & Dynamic Themes**:
  - Full **Dark**, **Light**, and **System-Adaptive** themes aligned with Windows 11 design guidelines.
  - High-contrast, crystal-clear typography with customized palette tokens.
  - Styled tables, rounded controls, responsive hover states, and smooth accent gradients.

- **📊 Real-Time Visual Status Feedback**:
  - Live per-package status tracking with color-coded badges:
    - 🟢 `✓ Upgraded` / `Installed` (Emerald Green)
    - 🔵 `● Update Available` (Accent Blue)
    - 🟣 `● Updating…` / `Installing…` (Sky Blue)
    - 🔴 `✕ Failed` (Crimson Red)
    - 🟠 `⚠ Mismatch` / `Up to date` (Amber / Orange)
    - ⚪ `Excluded` (Slate Muted)
  - Live progress indicators with elapsed timer and command previews.

- **💻 Activity & Terminal Log Viewer**:
  - Built-in live terminal dock with **Fira Code / Fira Mono** typography (11pt).
  - Streamed console outputs for all `winget` operations.
  - Color-coded log level tags:
    - `[INFO]` in vibrant green
    - `[WARN]` in bright yellow
    - `[ERROR]` and `[CRITICAL]` in bright red
    - `[DEBUG]` in muted slate
  - Formatted error tracebacks and global uncaught exception trapping.
  - One-click **Clear Logs** and **Copy Logs** actions.

- **⚡ Comprehensive Package Management**:
  - **Upgrade Selected**: Batch upgrade checked packages with detailed status reports.
  - **Upgrade All**: One-click full system software upgrade.
  - **Force Reinstall**: Force reinstall or repair stubborn applications.
  - **Uninstall**: Remove applications directly from the GUI.
  - **Upgrade PowerShell**: Specialized shortcut to keep Microsoft.PowerShell up-to-date.
  - **Package Details**: Inspect full `winget show` metadata in a formatted viewer.
  - **Right-Click Context Menu**: Quick access to upgrade, uninstall, view details, exclude, or copy package IDs/names.

- **🛡️ Powerful Exclusion Manager**:
  - Exclude packages by exact **Package ID** or **Wildcard Pattern** (e.g. `*adobe*`, `camtasia-*`).
  - Automatically filter unknown version tags or unstable drivers.
  - Exclusions stored in an atomic, validated JSON configuration with auto-backup on corruption.

- **🔄 Automatic Refresh**:
  - Seamlessly re-scans the package catalog after operations complete so the list is always up-to-date.

---

## 🏗️ Architecture & Project Structure

```text
winget_upgrade/
├── winget_gui/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Application entrypoint & elevation checks
│   ├── config.py            # ConfigManager with atomic saves & validation
│   ├── parser.py            # JSON and tabular parser for winget output
│   ├── winget.py            # Subprocess backend wrapping winget CLI
│   ├── workers.py           # Background QThread workers (Package, Operation, Info)
│   ├── resources/
│   │   └── updated.ico      # Application icon resource
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py   # Primary MainWindow & PackageModel implementation
│       ├── theme.py         # QSS stylesheets, QPalette generator, and color tokens
│       ├── exclusion_dialog.py # Exclusion management dialog
│       └── info_dialog.py   # Package information inspector
├── tests/
│   ├── test_config.py       # Atomic config save/load and backup tests
│   ├── test_parser.py       # Winget output parsing and localization tests
│   └── test_winget.py       # Worker signals, PackageModel, and theme unit tests
├── pyproject.toml           # Hatchling build configuration & dependencies
├── requirements.txt         # Pinned runtime and test dependencies
├── WingetUpgrade.spec       # PyInstaller standalone executable specification
└── pyinstaller_command.txt  # Command line build instructions
```

---

## 📦 Prerequisites

1. **Operating System**: Windows 10 (version 1809+) or Windows 11.
2. **Windows Package Manager**: Ensure `winget` is installed (included by default via App Installer).
3. **Python**: Python `>= 3.14`.
4. **Package Manager**: [uv](https://github.com/astral-sh/uv) (recommended) or standard `pip`.

---

## 🚀 Getting Started

### 1. Clone and Install Dependencies

Using `uv`:
```powershell
# Clone the repository
git clone <repo-url>
cd winget_upgrade

# Sync virtual environment and dependencies
uv sync
```

Using standard `pip`:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run the Application

```powershell
uv run winget-gui
```
*Or:*
```powershell
python -m winget_gui.main
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + F` | Focus the search filter input |
| `Space` | Toggle checkbox on the selected row |
| `Delete` | Add the selected package ID to exclusions |
| `Double Click` | Open Package Information dialog |

---

## 🧪 Testing

The repository uses **`pytest`** and **`pytest-qt`** for automated testing.

Run all tests:
```powershell
uv run pytest
```

Output:
```text
============================= test session starts =============================
collected 11 items

tests\test_config.py ...                                                 [ 27%]
tests\test_parser.py ...                                                 [ 54%]
tests\test_winget.py .....                                               [100%]

============================= 11 passed in 0.06s ==============================
```

---

## 🔨 Building Standalone Executable

To compile a single-file, standalone `.exe` using PyInstaller:

```powershell
uv run pyinstaller WingetUpgrade.spec
```

The compiled binary will be placed in `dist/WingetUpgrade.exe`.

---

## 📄 License

This project is licensed under the MIT License.
