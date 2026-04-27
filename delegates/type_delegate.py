from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QComboBox, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from delegates.value_formatting import _apply_type_style
from themes import LIGHT_DEFAULT
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.types import JsonType


class JsonTypeDelegate(QStyledItemDelegate):
    @staticmethod
    def _source_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        model = idx.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(idx)
        return idx

    @staticmethod
    def _find_tab(host) -> object | None:
        cursor = host
        while cursor is not None:
            if hasattr(cursor, "commit_set_data"):
                return cursor
            cursor = cursor.parent() if hasattr(cursor, "parent") else None
        return None

    def __init__(self, parent=None, *, theme: ThemeSpec | None = None):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        # ``_interactive`` is set to ``True`` for the duration of an
        # interactive (user-driven) commit out of the type combo. The
        # ``JsonTab._on_type_changed`` slot reads it to decide whether to
        # auto-reopen the value editor on the row whose type just changed.
        # Programmatic ``model.setData(...)`` calls bypass this delegate
        # entirely, so the flag stays ``False`` and no editor is reopened —
        # this is what keeps the smoke tests in
        # ``tests/test_smoke_mainwindow.py`` from logging
        # ``edit: editing failed``.
        self._interactive: bool = False

    def set_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        source_index = self._source_index(index)
        if not source_index.isValid():
            return
        item = source_index.internalPointer()
        if not isinstance(item, JsonTreeItem):
            return
        _apply_type_style(
            option,
            self._theme.types[item.json_type],
            selected=bool(option.state & QStyle.StateFlag.State_Selected),
            allow_background=False,
        )

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = QComboBox(parent)
        for tp in JsonType:
            editor.addItem(tp.value, tp)
        return editor

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        source_index = self._source_index(index)
        item: JsonTreeItem = source_index.internalPointer()
        idx = editor.findData(item.json_type)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        selected_type = editor.currentData()

        self._interactive = True
        try:
            tab = self._find_tab(editor)
            if tab is not None:
                tab.commit_set_data(index, selected_type, Qt.ItemDataRole.EditRole)
                return

            model.setData(index, selected_type, Qt.ItemDataRole.EditRole)
        finally:
            self._interactive = False
