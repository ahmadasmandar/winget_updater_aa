from PyQt6 import QtWidgets


class ExclusionDialog(QtWidgets.QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage exclusions")
        layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        self.ids = QtWidgets.QListWidget(); self.patterns = QtWidgets.QListWidget()
        self.ids.addItems(config.get("excluded_ids", [])); self.patterns.addItems(config.get("excluded_patterns", []))
        tabs.addTab(self.ids, "Excluded IDs")
        pattern_page = QtWidgets.QWidget(); pattern_layout = QtWidgets.QVBoxLayout(pattern_page)
        pattern_layout.addWidget(self.patterns); pattern_layout.addWidget(QtWidgets.QLabel("Patterns use case-insensitive fnmatch wildcards, e.g. *adobe* or camtasia-*."))
        tabs.removeTab(1); tabs.addTab(pattern_page, "Excluded patterns")
        layout.addWidget(tabs)
        for widget, label, handler in ((self.ids, "Add ID", self._add_id), (self.patterns, "Add pattern", self._add_pattern)):
            button = QtWidgets.QPushButton(label); button.clicked.connect(handler); layout.addWidget(button)
        remove = QtWidgets.QPushButton("Remove selected"); remove.clicked.connect(self._remove); layout.addWidget(remove)
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject); layout.addWidget(box)

    def _add_id(self):
        value, ok = QtWidgets.QInputDialog.getText(self, "Add excluded ID", "Package ID:")
        if ok and value.strip(): self.ids.addItem(value.strip())

    def _add_pattern(self):
        value, ok = QtWidgets.QInputDialog.getText(self, "Add excluded pattern", "Name pattern:")
        if ok and value.strip(): self.patterns.addItem(value.strip().lower())

    def _remove(self):
        widget = self.ids if self.ids.hasFocus() else self.patterns
        for item in widget.selectedItems(): widget.takeItem(widget.row(item))

    def values(self):
        return ([self.ids.item(i).text() for i in range(self.ids.count())], [self.patterns.item(i).text() for i in range(self.patterns.count())])

