from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSize, QSortFilterProxyModel, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from delegates.value_formatting import _apply_type_style
from themes import LIGHT_DEFAULT
from themes.icon_provider import IconProvider, StubIconProvider
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

    def __init__(
        self,
        parent=None,
        *,
        theme: ThemeSpec | None = None,
        icon_provider: IconProvider | None = None,
    ):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        self._icon_provider: IconProvider = icon_provider or StubIconProvider()
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
        self._active_type_edit_index: QPersistentModelIndex | None = None

    @staticmethod
    def _emit_icon_changed(index: QModelIndex | QPersistentModelIndex | None) -> None:
        if index is None:
            return
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        if not idx.isValid():
            return
        model = idx.model()
        if model is None:
            return
        type_idx = model.index(idx.row(), 1, idx.parent())
        if not type_idx.isValid():
            return
        model.dataChanged.emit(type_idx, type_idx, [Qt.ItemDataRole.DecorationRole])

    def _set_active_type_edit_index(self, source_index: QModelIndex) -> None:
        next_index = QPersistentModelIndex(source_index) if source_index.isValid() else None
        current_index = self._active_type_edit_index
        if current_index == next_index:
            return
        self._active_type_edit_index = next_index
        self._emit_icon_changed(current_index)
        self._emit_icon_changed(next_index)

    def _is_active_type_edit_index(self, source_index: QModelIndex) -> bool:
        if self._active_type_edit_index is None or not self._active_type_edit_index.isValid():
            return False
        return self._active_type_edit_index == QPersistentModelIndex(source_index)

    def set_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme

    def set_icon_provider(self, provider: IconProvider | None) -> None:
        self._icon_provider = provider or StubIconProvider()

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        source_index = self._source_index(index)
        if not source_index.isValid():
            return
        item = source_index.internalPointer()
        if not isinstance(item, JsonTreeItem):
            return
        if self._is_active_type_edit_index(source_index):
            # Keep only the combobox's icon visible while the type cell is in edit mode.
            option.icon = QIcon()
        _apply_type_style(
            option,
            self._theme.types[item.json_type],
            selected=bool(option.state & QStyle.StateFlag.State_Selected),
            allow_background=False,
        )

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = QComboBox(parent)
        icon_size = QSize(max(12, option.fontMetrics.height()), max(12, option.fontMetrics.height()))
        host_view = option.widget
        if host_view is not None and hasattr(host_view, "iconSize"):
            host_size = host_view.iconSize()
            if host_size.isValid():
                icon_size = host_size
        editor.setIconSize(icon_size)
        editor.view().setIconSize(icon_size)
        for tp in JsonType:
            editor.addItem(self._icon_provider.for_type(tp), tp.value, tp)
        self._set_active_type_edit_index(self._source_index(index))
        return editor

    def destroyEditor(self, editor: QWidget, index: QModelIndex) -> None:  # type: ignore[override]
        try:
            super().destroyEditor(editor, index)
        finally:
            source_index = self._source_index(index)
            if self._is_active_type_edit_index(source_index):
                self._set_active_type_edit_index(QModelIndex())

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
