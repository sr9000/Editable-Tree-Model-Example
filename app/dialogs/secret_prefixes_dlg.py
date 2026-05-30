from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class SecretPrefixesDialog(QDialog):
    def __init__(self, prefixes: Iterable[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Secret word prefixes")

        self.list_widget = QListWidget(self)
        for prefix in prefixes:
            self.list_widget.addItem(str(prefix))

        buttons_row = QHBoxLayout()
        self.add_btn = QPushButton("Add", self)
        self.edit_btn = QPushButton("Edit", self)
        self.remove_btn = QPushButton("Remove", self)
        buttons_row.addWidget(self.add_btn)
        buttons_row.addWidget(self.edit_btn)
        buttons_row.addWidget(self.remove_btn)

        self.ok_cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons_row)
        layout.addWidget(self.ok_cancel)

        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.remove_btn.clicked.connect(self._remove)
        self.ok_cancel.accepted.connect(self._accept_if_valid)
        self.ok_cancel.rejected.connect(self.reject)

    def prefixes(self) -> list[str]:
        return [self.list_widget.item(i).text().strip().lower() for i in range(self.list_widget.count())]

    def _add(self) -> None:
        text, ok = QInputDialog.getText(self, "Add prefix", "Prefix (lowercase word-start):")
        if not ok:
            return
        value = text.strip().lower()
        if value:
            self.list_widget.addItem(value)

    def _edit(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        text, ok = QInputDialog.getText(self, "Edit prefix", "Prefix (lowercase word-start):", text=item.text())
        if not ok:
            return
        value = text.strip().lower()
        if value:
            item.setText(value)

    def _remove(self) -> None:
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _accept_if_valid(self) -> None:
        if not any(self.prefixes()):
            QMessageBox.warning(self, "Invalid prefixes", "At least one prefix is required.")
            return
        self.accept()
