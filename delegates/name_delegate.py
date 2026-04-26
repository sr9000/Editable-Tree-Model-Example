from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import QLineEdit, QStyleOptionViewItem, QWidget

from delegates.base import _CapsLockSafeLineEdit, _TextEditorDelegateBase


def _find_tab(host) -> object | None:
    cursor = host
    while cursor is not None:
        if hasattr(cursor, "commit_set_data"):
            return cursor
        cursor = cursor.parent() if hasattr(cursor, "parent") else None
    return None


def _commit(index: QModelIndex, value, role: Qt.ItemDataRole, host=None) -> bool:
    model = index.model()
    if model is None:
        return False

    tab = _find_tab(host)
    if tab is not None:
        return bool(tab.commit_set_data(index, value, role))
    return bool(model.setData(index, value, role))


class NameDelegate(_TextEditorDelegateBase):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        return _CapsLockSafeLineEdit(parent)

    def setEditorData(self, editor: QLineEdit, index: QModelIndex):
        editor.setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QLineEdit, model: QAbstractItemModel, index: QModelIndex):
        _commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
