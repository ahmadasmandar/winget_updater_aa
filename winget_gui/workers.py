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
            self.progress.emit("Loading packages…")
            self.packages_ready.emit(self.backend.list_packages(self.is_cancelled))
        except Exception:
            self.logger.exception("Package refresh failed")
            self.error.emit(traceback.format_exc())


class OperationWorker(QtCore.QThread, CancelMixin):
    progress = QtCore.pyqtSignal(str)
    progress_step = QtCore.pyqtSignal(int, int, str)
    progress_count = QtCore.pyqtSignal(int, int)
    package_result = QtCore.pyqtSignal(str, str, str)
    finished_all = QtCore.pyqtSignal(int, int, int, int)

    def __init__(self, operations, backend=None, parent=None):
        QtCore.QThread.__init__(self, parent)
        CancelMixin.__init__(self)
        self.operations = operations
        self.backend = backend or WingetBackend()
        self.logger = logging.getLogger(__name__)

    def run(self):
        counts = [0, 0, 0, 0]
        for index, operation in enumerate(self.operations, 1):
            if self.is_cancelled():
                break
            args, package_id, label, *package_name = operation
            name = package_name[0] if package_name else package_id
            self.progress.emit(f"{label} {index}/{len(self.operations)}: {name} | {subprocess.list2cmdline(args)}")
            try:
                try:
                    code, output = self.backend.operation(args, cancelled=self.is_cancelled, visible=True)
                except TypeError as exc:
                    if "visible" not in str(exc): raise
                    code, output = self.backend.operation(args, cancelled=self.is_cancelled)
                self.logger.info("Operation return code for %s: %s", package_id, code)
                kind = WINGET_CODES.get(code & 0xFFFFFFFF, "failed")
                slot = {"success": 0, "no_applicable_upgrade": 2, "installer_technology_mismatch": 3}.get(kind, 1)
                counts[slot] += 1
                status = "success" if slot == 0 else "skipped" if slot == 2 else "mismatch" if slot == 3 else "failed"
                self.package_result.emit(package_id, status, output)
            except Exception as exc:
                self.logger.exception("Operation failed for %s", package_id)
                counts[1] += 1
                self.package_result.emit(package_id, "failed", str(exc))
            self.progress_count.emit(sum(counts), len(self.operations))
            self.progress_step.emit(index, len(self.operations), name)
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
            _, output = self.backend.info(self.package_id, self.is_cancelled)
            self.result_ready.emit(self.package_id, output)
        except Exception:
            self.logger.exception("Info query failed for %s", self.package_id)
            self.error.emit(traceback.format_exc())
