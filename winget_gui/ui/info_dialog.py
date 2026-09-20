from PyQt6 import QtWidgets, QtGui


def show_info(parent, package_id, output):
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(f"Package Information — {package_id}")
    dialog.resize(760, 560)
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(16, 16, 16, 16)

    title = QtWidgets.QLabel(f"Details: {package_id}")
    title.setStyleSheet("font-size: 12pt; font-weight: bold;")
    layout.addWidget(title)

    text = QtWidgets.QPlainTextEdit()
    text.setReadOnly(True)
    text.setPlainText(output)
    layout.addWidget(text)

    btn_row = QtWidgets.QHBoxLayout()
    copy_btn = QtWidgets.QPushButton("Copy to Clipboard")
    copy_btn.clicked.connect(lambda: QtGui.QGuiApplication.clipboard().setText(output))
    btn_row.addWidget(copy_btn)

    btn_row.addStretch()
    close_btn = QtWidgets.QPushButton("Close")
    close_btn.setObjectName("primaryBtn")
    close_btn.clicked.connect(dialog.accept)
    btn_row.addWidget(close_btn)

    layout.addLayout(btn_row)
    dialog.exec()
