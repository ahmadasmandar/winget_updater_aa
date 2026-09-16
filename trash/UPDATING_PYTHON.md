# How to Update Python Version in a `uv` Project

This guide explains how to change the Python version for your project (e.g., upgrading from 3.11 to 3.13).

## 1. Check Current Version

Check the python version currently used by your virtual environment:

```powershell
.venv\Scripts\python.exe --version
# OR if using uv directly
uv run python --version
```

## 2. Update Project Configuration

### Step A: Update `pyproject.toml`
If your project has a `pyproject.toml` file, update the `requires-python` field:

```toml
[project]
requires-python = ">=3.13"  # Change this to your desired version
```

### Step B: Pin the Version
Use `uv` to pin the specific version you want. This updates the `.python-version` file.

```powershell
uv python pin 3.13
```

## 3. Recreate Virtual Environment

Updating the Python version usually requires recreating the virtual environment.

> **⚠️ CRITICAL: Close all running applications**
> Before proceeding, ensure your mismatched python process (e.g., your GUI app or VS Code terminal) is **CLOSED**. If the file is in use, the update will fail with "Access Denied" errors.

Run the following commands to wipe the old environment and create a new one:

```powershell
# 1. Remove the old environment (force removal to handle read-only files)
Remove-Item -Path .venv -Recurse -Force

# 2. Create new venv with the specific python version
uv venv --python 3.13
```

## 4. Sync Dependencies

Install your project dependencies into the new environment:

```powershell
uv sync
```

## 5. Verify the Update

Check that the new environment is using the correct version:

```powershell
.venv\Scripts\python.exe --version
# Should output: Python 3.13.x
```

## Troubleshooting: "Access Denied" / "Zugriff verweigert"

If you see error 5 (Access Denied) when removing `.venv`:

1.  **Find the locked process**:
    ```powershell
    Get-Process python | Select-Object Id, Path
    ```
2.  **Kill the process** (Replace `1234` with the ID found above):
    ```powershell
    Stop-Process -Id 1234 -Force
    ```
3.  **Try removing `.venv` again**.
