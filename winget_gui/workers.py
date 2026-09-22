import logging
import subprocess
import traceback

from PyQt6 import QtCore

from .winget import WingetBackend, WINGET_CODES, WingetError


class CancelMixin:
    def __init__(self):
        self._mutex = QtCore.QMutex()
        self._cancelled = False

    def cancel(self):
        locker = QtCore.QMutexLocker(self._mutex)
        self._cancelled = True

    def is_cancelled(self):
        locker = QtCore.QMutexLocker(self._mutex)
        return self._cancelled


class PackageWorker(QtCore.QThread, CancelMixin):
    packages_ready = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(str)

    def __init__(self, backend=None, parent=None):
        QtCore.QThread.__init__(self, parent)
        CancelMixin.__init__(self)
        self.backend = backend or WingetBackend()
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            self.logger.info("Initializing package catalog scan via winget…")
            self.progress.emit("Loading packages…")
            packages = self.backend.list_packages(self.is_cancelled)
            self.logger.info("Package scan completed successfully: %d upgradable package(s) detected.", len(packages))
            for pkg in packages:
                self.logger.debug(
                    "Detected upgrade: '%s' [%s] Version: %s -> %s (Source: %s)",
                    pkg.get("Name", "Unknown"),
                    pkg.get("Id", "Unknown"),
                    pkg.get("Version", "Unknown"),
                    pkg.get("AvailableVersion", "Unknown"),
                    pkg.get("Source", "winget"),
                )
            self.packages_ready.emit(packages)
        except Exception as exc:
            self.logger.exception("Package refresh failed with error: %s", exc)
            self.error.emit(traceback.format_exc())


class OperationWorker(QtCore.QThread, CancelMixin):
    progress = QtCore.pyqtSignal(str)
    progress_step = QtCore.pyqtSignal(int, int, str)
    progress_count = QtCore.pyqtSignal(int, int)
    package_started = QtCore.pyqtSignal(str, str)
    package_result = QtCore.pyqtSignal(str, str, str)
    finished_all = QtCore.pyqtSignal(int, int, int, int)

    def __init__(self, operations, backend=None, parent=None, visible=True):
        QtCore.QThread.__init__(self, parent)
        CancelMixin.__init__(self)
        self.operations = operations
        self.backend = backend or WingetBackend()
        self.visible = visible
        self.logger = logging.getLogger(__name__)

    def run(self):
        counts = [0, 0, 0, 0]
        total_ops = len(self.operations)
        self.logger.info("Starting batch operations queue: %d total package operation(s) (terminal window visible: %s).", total_ops, self.visible)

        for index, operation in enumerate(self.operations, 1):
            if self.is_cancelled():
                self.logger.warning("Operation queue cancelled by user. Remaining operations: %d.", total_ops - index + 1)
                break
            args, package_id, label, *package_name = operation
            name = package_name[0] if package_name else package_id
            cmd_str = subprocess.list2cmdline(args)

            self.package_started.emit(package_id, label)
            self.logger.info("────────────────────────────────────────────────────────────────────────────")
            self.logger.info("[%d/%d] Starting %s: '%s' (ID: %s)", index, total_ops, label, name, package_id)
            self.logger.info("Executing command: %s", cmd_str)
            self.progress.emit(f"{label} {index}/{total_ops}: {name} | {cmd_str}")

            try:
                try:
                    code, output = self.backend.operation(args, cancelled=self.is_cancelled, visible=self.visible)
                except TypeError as exc:
                    if "visible" not in str(exc):
                        raise
                    code, output = self.backend.operation(args, cancelled=self.is_cancelled)

                if output:
                    for line in output.splitlines():
                        line_stripped = line.strip()
                        if line_stripped:
                            self.logger.info("[%s] %s", package_id, line_stripped)

                kind = WINGET_CODES.get(code & 0xFFFFFFFF, "failed" if code != 0 else "success")
                slot = {"success": 0, "no_applicable_upgrade": 2, "installer_technology_mismatch": 3}.get(kind, 1)
                counts[slot] += 1
                status = "success" if slot == 0 else "skipped" if slot == 2 else "mismatch" if slot == 3 else "failed"

                if status == "success":
                    self.logger.info("✓ [%s] %s completed successfully (Exit code: %s)", package_id, label, code)
                elif status == "skipped":
                    self.logger.warning("⚠ [%s] No applicable upgrade available (Exit code: 0x%X)", package_id, code & 0xFFFFFFFF)
                elif status == "mismatch":
                    self.logger.warning("⚠ [%s] Installer technology mismatch (Exit code: 0x%X)", package_id, code & 0xFFFFFFFF)
                else:
                    self.logger.error("✕ [%s] %s failed with exit code: %s", package_id, label, code)

                self.package_result.emit(package_id, status, output)
            except Exception as exc:
                self.logger.exception("✕ [%s] Operation exception during %s: %s", package_id, label, exc)
                counts[1] += 1
                self.package_result.emit(package_id, "failed", str(exc))

            self.progress_count.emit(sum(counts), total_ops)
            self.progress_step.emit(index, total_ops, name)

        self.logger.info("────────────────────────────────────────────────────────────────────────────")
        self.logger.info(
            "Batch execution finished: %d succeeded, %d failed, %d skipped, %d mismatched.",
            counts[0], counts[1], counts[2], counts[3]
        )
        self.finished_all.emit(*counts)


class InfoWorker(QtCore.QThread, CancelMixin):
    result_ready = QtCore.pyqtSignal(str, str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, package_id, backend=None, parent=None):
        QtCore.QThread.__init__(self, parent)
        CancelMixin.__init__(self)
        self.package_id = package_id
        self.backend = backend or WingetBackend()
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            self.logger.info("Querying detailed package metadata for ID: %s", self.package_id)
            code, output = self.backend.info(self.package_id, self.is_cancelled)
            self.logger.info("Package metadata query finished for %s (exit code: %s)", self.package_id, code)
            self.result_ready.emit(self.package_id, output)
        except Exception as exc:
            self.logger.exception("Failed to query package info for %s: %s", self.package_id, exc)
            self.error.emit(traceback.format_exc())
