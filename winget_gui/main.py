import sys
if sys.platform != "win32": sys.exit("Winget GUI is supported on Windows only.")

import ctypes
import logging
import subprocess
from PyQt6 import QtWidgets


def is_admin():
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError): return False


def relaunch_as_admin():
    executable = sys.executable; args = sys.argv[1:] if getattr(sys, "frozen", False) else [sys.argv[0], *sys.argv[1:]]
    try: return int(ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, subprocess.list2cmdline(args), None, 1)) > 32
    except (OSError, ValueError): return False


def main():
    app = QtWidgets.QApplication(sys.argv); app.setStyle("Fusion")
    if not is_admin():
        dialog = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Warning, "Administrator access", "Administrator access is required for package operations.")
        run = dialog.addButton("Run unelevated", QtWidgets.QMessageBox.ButtonRole.AcceptRole); dialog.addButton("Exit", QtWidgets.QMessageBox.ButtonRole.RejectRole); dialog.exec()
        if dialog.clickedButton() is not run: return 1
    try:
        from winget_gui.ui.main_window import MainWindow
    except Exception as exc:
        logging.exception("Startup failed")
        QtWidgets.QMessageBox.critical(None, "Startup error", str(exc)); return 1
    window = MainWindow(); window.show(); return app.exec()


if __name__ == "__main__": sys.exit(main())
