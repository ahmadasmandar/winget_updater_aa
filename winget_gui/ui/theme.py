import os
import sys
import winreg
from PyQt6 import QtCore, QtGui, QtWidgets


def resource_path(relative_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base, relative_path)


def icon(name):
    # Standard system icon fallback or custom resource
    resource = resource_path("resources/updated.ico")
    if os.path.exists(resource):
        return QtGui.QIcon(resource)
    return QtGui.QIcon.fromTheme(name)


def get_system_theme():
    """Detect Windows light/dark mode preference from registry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "Light" if value == 1 else "Dark"
    except Exception:
        return "Dark"


def resolve_theme_mode(mode):
    if mode == "System":
        return get_system_theme()
    return "Light" if mode == "Light" else "Dark"


STATUS_COLORS = {
    "Dark": {
        "success": QtGui.QColor("#10B981"),       # Emerald Green
        "failed": QtGui.QColor("#EF4444"),        # Crimson Red
        "in_progress": QtGui.QColor("#38BDF8"),   # Sky Blue
        "skipped": QtGui.QColor("#F59E0B"),       # Amber
        "mismatch": QtGui.QColor("#F97316"),      # Orange
        "available": QtGui.QColor("#60A5FA"),     # Accent Blue
        "excluded": QtGui.QColor("#94A3B8"),      # Slate Muted
        "default": QtGui.QColor("#E2E8F0"),       # Light Slate
    },
    "Light": {
        "success": QtGui.QColor("#059669"),       # Darker Emerald
        "failed": QtGui.QColor("#DC2626"),        # Darker Red
        "in_progress": QtGui.QColor("#0284C7"),   # Cyan/Blue
        "skipped": QtGui.QColor("#D97706"),       # Amber
        "mismatch": QtGui.QColor("#EA580C"),      # Orange
        "available": QtGui.QColor("#2563EB"),     # Deep Blue
        "excluded": QtGui.QColor("#64748B"),      # Slate Muted
        "default": QtGui.QColor("#0F172A"),       # Dark Slate
    },
}


def get_status_color(status_key, mode="Dark"):
    theme_key = resolve_theme_mode(mode)
    colors = STATUS_COLORS.get(theme_key, STATUS_COLORS["Dark"])
    return colors.get(status_key, colors["default"])


def stylesheet(mode="Dark"):
    resolved = resolve_theme_mode(mode)
    if resolved == "Dark":
        return """
        /* ==================== GLOBAL ==================== */
        QWidget {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', system-ui, sans-serif;
            font-size: 10pt;
            color: #F3F4F6;
            background-color: #12131C;
        }

        QMainWindow {
            background-color: #12131C;
        }

        /* ==================== BUTTONS ==================== */
        QPushButton {
            background-color: #222332;
            color: #F3F4F6;
            border: 1px solid #32344A;
            border-radius: 6px;
            padding: 6px 14px;
            min-height: 24px;
            font-weight: 500;
        }

        QPushButton:hover {
            background-color: #2D2F44;
            border-color: #4C5070;
            color: #FFFFFF;
        }

        QPushButton:pressed {
            background-color: #1B1C29;
            border-color: #3B82F6;
        }

        QPushButton:disabled {
            background-color: #181924;
            color: #525570;
            border-color: #252636;
        }

        QPushButton#primaryBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #3B82F6);
            color: #FFFFFF;
            border: 1px solid #1D4ED8;
            font-weight: 600;
        }

        QPushButton#primaryBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB);
            border-color: #60A5FA;
        }

        QPushButton#primaryBtn:pressed {
            background: #1E40AF;
        }

        QPushButton#primaryBtn:disabled {
            background: #1E293B;
            color: #475569;
            border-color: #1E293B;
        }

        QPushButton#dangerBtn {
            background-color: #2D1C22;
            color: #F87171;
            border: 1px solid #54222C;
            font-weight: 500;
        }

        QPushButton#dangerBtn:hover {
            background-color: #DC2626;
            color: #FFFFFF;
            border-color: #EF4444;
        }

        QPushButton#dangerBtn:pressed {
            background-color: #991B1B;
        }

        QPushButton#dangerBtn:disabled {
            background-color: #181924;
            color: #525570;
            border-color: #252636;
        }

        QPushButton#accentBtn {
            background-color: #1E2640;
            color: #60A5FA;
            border: 1px solid #283B66;
            font-weight: 600;
        }

        QPushButton#accentBtn:hover {
            background-color: #2563EB;
            color: #FFFFFF;
            border-color: #3B82F6;
        }

        /* ==================== LINE EDIT / SEARCH ==================== */
        QLineEdit {
            background-color: #1A1B28;
            color: #F3F4F6;
            border: 1px solid #32344A;
            border-radius: 6px;
            padding: 6px 12px;
            selection-background-color: #2563EB;
            selection-color: #FFFFFF;
        }

        QLineEdit:hover {
            border-color: #4C5070;
        }

        QLineEdit:focus {
            border: 1px solid #3B82F6;
            background-color: #1E1F2E;
        }

        /* ==================== TABLE VIEW ==================== */
        QTableView {
            background-color: #181926;
            alternate-background-color: #1C1D2C;
            color: #F3F4F6;
            gridline-color: #27283A;
            border: 1px solid #2D2F44;
            border-radius: 6px;
            selection-background-color: #233866;
            selection-color: #FFFFFF;
            outline: none;
        }

        QTableView::item {
            padding: 7px 10px;
            border: none;
        }

        QTableView::item:hover {
            background-color: #23253A;
        }

        QTableView::item:selected {
            background-color: #1E3A8A;
            color: #FFFFFF;
        }

        QHeaderView {
            background-color: #131420;
        }

        QHeaderView::section {
            background-color: #141522;
            color: #94A3B8;
            font-weight: 600;
            font-size: 9pt;
            padding: 8px 10px;
            border: none;
            border-bottom: 2px solid #2D2F44;
            border-right: 1px solid #212234;
        }

        QHeaderView::section:hover {
            background-color: #1A1C2C;
            color: #F3F4F6;
        }

        /* ==================== PROGRESS BAR ==================== */
        QProgressBar {
            background-color: #1A1B28;
            border: 1px solid #2D2F44;
            border-radius: 6px;
            text-align: center;
            color: #F3F4F6;
            font-weight: 600;
            font-size: 8.5pt;
            min-height: 16px;
            max-height: 16px;
        }

        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #6366F1);
            border-radius: 5px;
        }

        /* ==================== LOG / PLAIN TEXT ==================== */
        QPlainTextEdit, QTextEdit {
            background-color: #0E0F17;
            color: #E2E8F0;
            border: 1px solid #262738;
            border-radius: 6px;
            padding: 10px;
            font-family: 'Fira Code', 'Fira Mono', 'Cascadia Code', 'Consolas', 'Segoe UI Mono', monospace;
            font-size: 11pt;
            font-weight: 450;
            line-height: 1.5;
            selection-background-color: #2563EB;
            selection-color: #FFFFFF;
        }

        /* ==================== DOCK WIDGET ==================== */
        QDockWidget {
            color: #F3F4F6;
            font-weight: 600;
        }

        QDockWidget::title {
            background-color: #181926;
            color: #CBD5E1;
            padding: 7px 12px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border: 1px solid #2D2F44;
            border-bottom: none;
            font-weight: 600;
        }

        /* ==================== MENUS & MENU BAR ==================== */
        QMenuBar {
            background-color: #12131C;
            color: #F3F4F6;
            border-bottom: 1px solid #262738;
            padding: 3px 6px;
        }

        QMenuBar::item {
            background-color: transparent;
            color: #E2E8F0;
            padding: 4px 10px;
            border-radius: 4px;
        }

        QMenuBar::item:selected {
            background-color: #222332;
            color: #FFFFFF;
        }

        QMenu {
            background-color: #1A1B28;
            color: #F3F4F6;
            border: 1px solid #32344A;
            border-radius: 6px;
            padding: 5px;
        }

        QMenu::item {
            padding: 6px 28px 6px 14px;
            border-radius: 4px;
            color: #E2E8F0;
        }

        QMenu::item:selected {
            background-color: #2563EB;
            color: #FFFFFF;
        }

        QMenu::separator {
            height: 1px;
            background-color: #2E3046;
            margin: 4px 6px;
        }

        /* ==================== SCROLLBARS ==================== */
        QScrollBar:vertical {
            background-color: #12131C;
            width: 10px;
            margin: 0px;
            border-radius: 5px;
        }

        QScrollBar::handle:vertical {
            background-color: #2E3046;
            min-height: 28px;
            border-radius: 5px;
            margin: 2px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #474A6C;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QScrollBar:horizontal {
            background-color: #12131C;
            height: 10px;
            margin: 0px;
            border-radius: 5px;
        }

        QScrollBar::handle:horizontal {
            background-color: #2E3046;
            min-width: 28px;
            border-radius: 5px;
            margin: 2px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #474A6C;
        }

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* ==================== DIALOGS & TABS ==================== */
        QDialog {
            background-color: #141520;
            color: #F3F4F6;
        }

        QTabWidget::pane {
            border: 1px solid #2D2F44;
            border-radius: 6px;
            background-color: #181926;
            padding: 8px;
        }

        QTabBar::tab {
            background-color: #141522;
            color: #94A3B8;
            padding: 8px 16px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }

        QTabBar::tab:selected {
            background-color: #181926;
            color: #FFFFFF;
            font-weight: 600;
            border-bottom: 2px solid #3B82F6;
        }

        QListWidget {
            background-color: #141520;
            color: #F3F4F6;
            border: 1px solid #2D2F44;
            border-radius: 6px;
            padding: 4px;
        }

        QListWidget::item {
            padding: 6px 10px;
            border-radius: 4px;
            color: #F3F4F6;
        }

        QListWidget::item:hover {
            background-color: #23253A;
        }

        QListWidget::item:selected {
            background-color: #1E3A8A;
            color: #FFFFFF;
        }

        /* ==================== BADGES & LABELS ==================== */
        QLabel {
            color: #F3F4F6;
            background: transparent;
        }

        QLabel#mutedLabel {
            color: #94A3B8;
            font-size: 9pt;
        }

        QLabel#commandLabel {
            background-color: #1A1B28;
            color: #38BDF8;
            border: 1px solid #2B2C3F;
            border-radius: 4px;
            padding: 3px 8px;
            font-family: 'Consolas', 'Segoe UI Mono', monospace;
            font-size: 8.5pt;
        }

        QLabel#badgeLabel {
            background-color: #1E293B;
            color: #93C5FD;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 2px 10px;
            font-size: 8.5pt;
            font-weight: 600;
        }

        QToolTip {
            background-color: #1E2030;
            color: #F3F4F6;
            border: 1px solid #3E425F;
            border-radius: 4px;
            padding: 5px 8px;
        }
        """
    else:
        # ==================== LIGHT THEME ====================
        return """
        /* ==================== GLOBAL ==================== */
        QWidget {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', system-ui, sans-serif;
            font-size: 10pt;
            color: #0F172A;
            background-color: #F8FAFC;
        }

        QMainWindow {
            background-color: #F8FAFC;
        }

        /* ==================== BUTTONS ==================== */
        QPushButton {
            background-color: #FFFFFF;
            color: #0F172A;
            border: 1px solid #D1D5DB;
            border-radius: 6px;
            padding: 6px 14px;
            min-height: 24px;
            font-weight: 500;
        }

        QPushButton:hover {
            background-color: #F3F4F6;
            border-color: #9CA3AF;
            color: #000000;
        }

        QPushButton:pressed {
            background-color: #E5E7EB;
            border-color: #2563EB;
        }

        QPushButton:disabled {
            background-color: #F3F4F6;
            color: #9CA3AF;
            border-color: #E5E7EB;
        }

        QPushButton#primaryBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #2563EB);
            color: #FFFFFF;
            border: 1px solid #1E40AF;
            font-weight: 600;
        }

        QPushButton#primaryBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E40AF, stop:1 #1D4ED8);
            border-color: #3B82F6;
        }

        QPushButton#primaryBtn:pressed {
            background: #172554;
        }

        QPushButton#primaryBtn:disabled {
            background: #E2E8F0;
            color: #94A3B8;
            border-color: #E2E8F0;
        }

        QPushButton#dangerBtn {
            background-color: #FEF2F2;
            color: #DC2626;
            border: 1px solid #FECACA;
            font-weight: 500;
        }

        QPushButton#dangerBtn:hover {
            background-color: #DC2626;
            color: #FFFFFF;
            border-color: #B91C1C;
        }

        QPushButton#dangerBtn:pressed {
            background-color: #991B1B;
        }

        QPushButton#dangerBtn:disabled {
            background-color: #F3F4F6;
            color: #9CA3AF;
            border-color: #E5E7EB;
        }

        QPushButton#accentBtn {
            background-color: #EFF6FF;
            color: #1D4ED8;
            border: 1px solid #BFDBFE;
            font-weight: 600;
        }

        QPushButton#accentBtn:hover {
            background-color: #2563EB;
            color: #FFFFFF;
            border-color: #1D4ED8;
        }

        /* ==================== LINE EDIT / SEARCH ==================== */
        QLineEdit {
            background-color: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 6px 12px;
            selection-background-color: #2563EB;
            selection-color: #FFFFFF;
        }

        QLineEdit:hover {
            border-color: #94A3B8;
        }

        QLineEdit:focus {
            border: 1px solid #2563EB;
            background-color: #FFFFFF;
        }

        /* ==================== TABLE VIEW ==================== */
        QTableView {
            background-color: #FFFFFF;
            alternate-background-color: #F8FAFC;
            color: #0F172A;
            gridline-color: #E2E8F0;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            selection-background-color: #DBEAFE;
            selection-color: #1E3A8A;
            outline: none;
        }

        QTableView::item {
            padding: 7px 10px;
            border: none;
        }

        QTableView::item:hover {
            background-color: #F1F5F9;
        }

        QTableView::item:selected {
            background-color: #DBEAFE;
            color: #1E3A8A;
        }

        QHeaderView {
            background-color: #F1F5F9;
        }

        QHeaderView::section {
            background-color: #F1F5F9;
            color: #475569;
            font-weight: 600;
            font-size: 9pt;
            padding: 8px 10px;
            border: none;
            border-bottom: 2px solid #CBD5E1;
            border-right: 1px solid #E2E8F0;
        }

        QHeaderView::section:hover {
            background-color: #E2E8F0;
            color: #0F172A;
        }

        /* ==================== PROGRESS BAR ==================== */
        QProgressBar {
            background-color: #E2E8F0;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            text-align: center;
            color: #0F172A;
            font-weight: 600;
            font-size: 8.5pt;
            min-height: 16px;
            max-height: 16px;
        }

        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #4F46E5);
            border-radius: 5px;
        }

        /* ==================== LOG / PLAIN TEXT ==================== */
        QPlainTextEdit, QTextEdit {
            background-color: #F8FAFC;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 10px;
            font-family: 'Fira Code', 'Fira Mono', 'Cascadia Code', 'Consolas', 'Segoe UI Mono', monospace;
            font-size: 11pt;
            font-weight: 450;
            line-height: 1.5;
            selection-background-color: #2563EB;
            selection-color: #FFFFFF;
        }

        /* ==================== DOCK WIDGET ==================== */
        QDockWidget {
            color: #0F172A;
            font-weight: 600;
        }

        QDockWidget::title {
            background-color: #F1F5F9;
            color: #334155;
            padding: 7px 12px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border: 1px solid #CBD5E1;
            border-bottom: none;
            font-weight: 600;
        }

        /* ==================== MENUS & MENU BAR ==================== */
        QMenuBar {
            background-color: #F8FAFC;
            color: #0F172A;
            border-bottom: 1px solid #E2E8F0;
            padding: 3px 6px;
        }

        QMenuBar::item {
            background-color: transparent;
            color: #334155;
            padding: 4px 10px;
            border-radius: 4px;
        }

        QMenuBar::item:selected {
            background-color: #E2E8F0;
            color: #0F172A;
        }

        QMenu {
            background-color: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 5px;
        }

        QMenu::item {
            padding: 6px 28px 6px 14px;
            border-radius: 4px;
            color: #0F172A;
        }

        QMenu::item:selected {
            background-color: #2563EB;
            color: #FFFFFF;
        }

        QMenu::separator {
            height: 1px;
            background-color: #E2E8F0;
            margin: 4px 6px;
        }

        /* ==================== SCROLLBARS ==================== */
        QScrollBar:vertical {
            background-color: #F8FAFC;
            width: 10px;
            margin: 0px;
            border-radius: 5px;
        }

        QScrollBar::handle:vertical {
            background-color: #CBD5E1;
            min-height: 28px;
            border-radius: 5px;
            margin: 2px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #94A3B8;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QScrollBar:horizontal {
            background-color: #F8FAFC;
            height: 10px;
            margin: 0px;
            border-radius: 5px;
        }

        QScrollBar::handle:horizontal {
            background-color: #CBD5E1;
            min-width: 28px;
            border-radius: 5px;
            margin: 2px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #94A3B8;
        }

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* ==================== DIALOGS & TABS ==================== */
        QDialog {
            background-color: #F8FAFC;
            color: #0F172A;
        }

        QTabWidget::pane {
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            background-color: #FFFFFF;
            padding: 8px;
        }

        QTabBar::tab {
            background-color: #F1F5F9;
            color: #64748B;
            padding: 8px 16px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }

        QTabBar::tab:selected {
            background-color: #FFFFFF;
            color: #0F172A;
            font-weight: 600;
            border-bottom: 2px solid #2563EB;
        }

        QListWidget {
            background-color: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 4px;
        }

        QListWidget::item {
            padding: 6px 10px;
            border-radius: 4px;
            color: #0F172A;
        }

        QListWidget::item:hover {
            background-color: #F1F5F9;
        }

        QListWidget::item:selected {
            background-color: #DBEAFE;
            color: #1E3A8A;
        }

        /* ==================== BADGES & LABELS ==================== */
        QLabel {
            color: #0F172A;
            background: transparent;
        }

        QLabel#mutedLabel {
            color: #64748B;
            font-size: 9pt;
        }

        QLabel#commandLabel {
            background-color: #F1F5F9;
            color: #0369A1;
            border: 1px solid #E2E8F0;
            border-radius: 4px;
            padding: 3px 8px;
            font-family: 'Consolas', 'Segoe UI Mono', monospace;
            font-size: 8.5pt;
        }

        QLabel#badgeLabel {
            background-color: #EFF6FF;
            color: #1D4ED8;
            border: 1px solid #BFDBFE;
            border-radius: 10px;
            padding: 2px 10px;
            font-size: 8.5pt;
            font-weight: 600;
        }

        QToolTip {
            background-color: #FFFFFF;
            color: #0F172A;
            border: 1px solid #CBD5E1;
            border-radius: 4px;
            padding: 5px 8px;
        }
        """


def apply_theme(application, mode):
    resolved = resolve_theme_mode(mode)
    palette = QtGui.QPalette()

    if resolved == "Dark":
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#12131C"))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#F3F4F6"))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#181926"))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#1C1D2C"))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#1E2030"))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#F3F4F6"))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#F3F4F6"))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#222332"))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#F3F4F6"))
        palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor("#38BDF8"))
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#2563EB"))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor("#64748B"))
    else:
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#F8FAFC"))
        palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#0F172A"))
        palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#F8FAFC"))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#0F172A"))
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#0F172A"))
        palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#0F172A"))
        palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor("#2563EB"))
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#3B82F6"))
        palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#FFFFFF"))
        palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor("#94A3B8"))

    application.setPalette(palette)
    application.setStyleSheet(stylesheet(mode))
