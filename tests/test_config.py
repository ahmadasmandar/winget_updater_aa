import json

from PyQt6 import QtCore

from winget_gui.config import ConfigManager


def test_atomic_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(QtCore.QStandardPaths, "writableLocation", lambda _: str(tmp_path))
    manager = ConfigManager()
    manager.save({"excluded_ids": ["Vendor.App"], "excluded_patterns": ["*adobe*"]})
    assert manager.load()["excluded_ids"] == ["Vendor.App"]
    assert not manager.path.with_suffix(".json.tmp").exists()


def test_corrupt_file_is_backed_up(tmp_path, monkeypatch):
    monkeypatch.setattr(QtCore.QStandardPaths, "writableLocation", lambda _: str(tmp_path))
    manager = ConfigManager(); manager.path.write_text("{bad", encoding="utf-8")
    assert manager.load()["excluded_ids"]
    assert manager.path.with_suffix(".json.bak").exists()


def test_invalid_exclusion_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(QtCore.QStandardPaths, "writableLocation", lambda _: str(tmp_path))
    manager = ConfigManager(); manager.path.write_text(json.dumps({"excluded_ids": ["ok.App", "bad id"]}), encoding="utf-8")
    assert manager.load()["excluded_ids"] == ["ok.App"]

