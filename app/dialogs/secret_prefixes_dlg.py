from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import (
    QDialog,
    QInputDialog,
    QMessageBox,
)

from ui.dialogs import Ui_SecretPrefixesDialog


class SecretPrefixesDialog(QDialog):
    def __init__(self, prefixes: Iterable[str], parent=None):
        super().__init__(parent)
        self._ui = Ui_SecretPrefixesDialog()
        self._ui.setupUi(self)

        self.list_widget = self._ui.listWidget
        self.add_btn = self._ui.addButton
        self.edit_btn = self._ui.editButton
        self.remove_btn = self._ui.removeButton
        self.ok_cancel = self._ui.buttonBox

        for prefix in prefixes:
            self.list_widget.addItem(str(prefix))


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
