from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QFont, QFontDatabase
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self._monospace_fields_enabled = False
        self._mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        self._monospace_fields_enabled = bool(enabled)

    def _apply_monospace_font(self, font: QFont) -> QFont:
        if not self._monospace_fields_enabled:
            return font
        f = QFont(font)
        f.setFamily(self._mono_family)
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setFixedPitch(True)
        return f

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        option.font = self._apply_monospace_font(option.font)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = _CapsLockSafeLineEdit(parent)
        editor.setFont(self._apply_monospace_font(editor.font()))
        return editor

    def setEditorData(self, editor: QLineEdit, index: QModelIndex):
        editor.setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QLineEdit, model: QAbstractItemModel, index: QModelIndex):
        _commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
