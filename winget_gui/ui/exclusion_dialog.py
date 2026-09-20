from PyQt6 import QtCore, QtWidgets


class ExclusionDialog(QtWidgets.QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Exclusions")
        self.resize(560, 480)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QtWidgets.QLabel("Package Exclusions")
        header.setStyleSheet("font-size: 12pt; font-weight: bold;")
        layout.addWidget(header)

        tabs = QtWidgets.QTabWidget()
        self.ids = QtWidgets.QListWidget()
        self.patterns = QtWidgets.QListWidget()

        self.ids.addItems(config.get("excluded_ids", []))
        self.patterns.addItems(config.get("excluded_patterns", []))

        # IDs Tab
        id_page = QtWidgets.QWidget()
        id_layout = QtWidgets.QVBoxLayout(id_page)
        id_layout.setContentsMargins(8, 8, 8, 8)
        id_layout.addWidget(QtWidgets.QLabel("Packages with these exact IDs will not appear in the upgrade list:"))
        id_layout.addWidget(self.ids)
        add_id_btn = QtWidgets.QPushButton("+ Add Package ID")
        add_id_btn.setObjectName("accentBtn")
        add_id_btn.clicked.connect(self._add_id)
        id_layout.addWidget(add_id_btn)
        tabs.addTab(id_page, "Excluded Package IDs")

        # Patterns Tab
        pattern_page = QtWidgets.QWidget()
        pattern_layout = QtWidgets.QVBoxLayout(pattern_page)
        pattern_layout.setContentsMargins(8, 8, 8, 8)
        pattern_layout.addWidget(QtWidgets.QLabel("Wildcard patterns (e.g. *adobe*, visualstudio*, *driver*):"))
        pattern_layout.addWidget(self.patterns)
        add_pattern_btn = QtWidgets.QPushButton("+ Add Wildcard Pattern")
        add_pattern_btn.setObjectName("accentBtn")
        add_pattern_btn.clicked.connect(self._add_pattern)
        pattern_layout.addWidget(add_pattern_btn)
        tabs.addTab(pattern_page, "Excluded Wildcard Patterns")

        layout.addWidget(tabs)

        btn_row = QtWidgets.QHBoxLayout()
        remove_btn = QtWidgets.QPushButton("Remove Selected")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.clicked.connect(self._remove)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setObjectName("primaryBtn")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        btn_row.addWidget(box)
        layout.addLayout(btn_row)

    def _add_id(self):
        value, ok = QtWidgets.QInputDialog.getText(self, "Add Excluded ID", "Enter exact Package ID (e.g. Mozilla.Firefox):")
        if ok and value.strip():
            self.ids.addItem(value.strip())

    def _add_pattern(self):
        value, ok = QtWidgets.QInputDialog.getText(self, "Add Excluded Pattern", "Enter pattern wildcard (e.g. *adobe*):")
        if ok and value.strip():
            self.patterns.addItem(value.strip().lower())

    def _remove(self):
        tab_idx = self.findChild(QtWidgets.QTabWidget).currentIndex()
        widget = self.ids if tab_idx == 0 else self.patterns
        for item in widget.selectedItems():
            widget.takeItem(widget.row(item))

    def values(self):
        return (
            [self.ids.item(i).text() for i in range(self.ids.count())],
            [self.patterns.item(i).text() for i in range(self.patterns.count())],
        )
