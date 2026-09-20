from PyQt6 import QtWidgets


def show_info(parent, package_id, output):
    dialog = QtWidgets.QDialog(parent); dialog.setWindowTitle(f"Package info: {package_id}"); dialog.resize(720, 520)
    layout = QtWidgets.QVBoxLayout(dialog); text = QtWidgets.QPlainTextEdit(); text.setReadOnly(True); text.setPlainText(output); layout.addWidget(text)
    close = QtWidgets.QPushButton("Close"); close.clicked.connect(dialog.accept); layout.addWidget(close); dialog.exec()

