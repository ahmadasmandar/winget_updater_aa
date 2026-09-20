import json
import logging
import os
import re
from pathlib import Path

from PyQt6 import QtCore

DEFAULT_CONFIG = {
    "excluded_patterns": ["adobe", "camtasia", "antigravity"],
    "excluded_ids": [
        "Microsoft.VisualStudio.2022.BuildTools",
        "Microsoft.DotNet.Framework.DeveloperPack",
    ],
    "exclude_unknown_versions": True,
}
_validate_ids = re.compile(r"^[A-Za-z0-9._+\-]{3,}$")


class ConfigManager(QtCore.QObject):
    warning = QtCore.pyqtSignal(str)

    def __init__(self, app_name="WingetUpgrade", logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger or logging.getLogger(__name__)
        root = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.AppConfigLocation)
        self.path = Path(root) / app_name / "config.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.path.exists():
            return dict(DEFAULT_CONFIG)
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
            config = {**DEFAULT_CONFIG, **raw}
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            backup = self.path.with_suffix(".json.bak")
            try:
                os.replace(self.path, backup)
            except OSError:
                self.logger.exception("Could not back up invalid config")
                raise
            message = f"Invalid configuration was backed up to {backup}; defaults are being used."
            self.logger.warning("%s Cause: %s", message, exc)
            self.warning.emit(message)
            return dict(DEFAULT_CONFIG)
        valid_ids = []
        for package_id in config.get("excluded_ids", []):
            if isinstance(package_id, str) and _validate_ids.fullmatch(package_id):
                valid_ids.append(package_id)
            else:
                self.logger.warning("Dropped invalid excluded ID: %r", package_id)
                self.warning.emit(f"Dropped invalid excluded ID: {package_id!r}")
        config["excluded_ids"] = valid_ids
        config["excluded_patterns"] = [str(value) for value in config.get("excluded_patterns", [])]
        config["exclude_unknown_versions"] = bool(config.get("exclude_unknown_versions", True))
        return config

    def save(self, config):
        payload = {**DEFAULT_CONFIG, **config}
        valid_ids = [value for value in payload["excluded_ids"] if isinstance(value, str) and _validate_ids.fullmatch(value)]
        payload["excluded_ids"] = valid_ids
        temporary = self.path.with_suffix(".json.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError:
            self.logger.exception("Could not save configuration")
            raise

