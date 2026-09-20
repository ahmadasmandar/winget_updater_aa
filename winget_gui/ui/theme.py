import os
import sys
from PyQt6 import QtGui


def icon(name):
    resource = resource_path("resources/updated.ico")
    return QtGui.QIcon(resource) if os.path.exists(resource) else QtGui.QIcon.fromTheme(name)


def resource_path(relative_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base, relative_path)


def stylesheet():
    return """QWidget { font-family: 'Segoe UI'; font-size: 10pt; }
QPushButton { padding: 5px 10px; min-height: 24px; }
QLineEdit, QPlainTextEdit { padding: 4px; }
QTableView::item { padding: 4px; }
QHeaderView::section { padding: 5px 7px; }
QProgressBar { min-height: 12px; max-height: 12px; }"""


def apply_theme(application, mode):
    if mode == "System":
        application.setPalette(application.style().standardPalette())
        return
    palette = application.style().standardPalette()
    if mode == "Dark":
        colors = {QtGui.QPalette.ColorRole.Window: "#292929", QtGui.QPalette.ColorRole.WindowText: "#e6e6e6", QtGui.QPalette.ColorRole.Base: "#202020", QtGui.QPalette.ColorRole.AlternateBase: "#292929", QtGui.QPalette.ColorRole.Text: "#e6e6e6", QtGui.QPalette.ColorRole.Button: "#333333", QtGui.QPalette.ColorRole.ButtonText: "#e6e6e6", QtGui.QPalette.ColorRole.Highlight: "#536b80", QtGui.QPalette.ColorRole.HighlightedText: "#ffffff", QtGui.QPalette.ColorRole.ToolTipBase: "#333333", QtGui.QPalette.ColorRole.ToolTipText: "#e6e6e6"}
        for role, color in colors.items(): palette.setColor(role, QtGui.QColor(color))
    else:
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#ffffff")); palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#f7f7f7"))
    application.setPalette(palette)
