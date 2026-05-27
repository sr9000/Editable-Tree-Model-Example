from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSize, QSortFilterProxyModel, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from delegates.base import paint_editor_underlay
from delegates.edit_context import DefaultEditContext, DelegateEditContext, EditResult
from delegates.value_formatting import _apply_type_style
from themes import LIGHT_DEFAULT
from themes.icon_provider import IconProvider, StubIconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.types import USER_SELECTABLE_TYPES, canonical_text_type


class JsonTypeDelegate(QStyledItemDelegate):
    @staticmethod
    def _source_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        model = idx.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(idx)
        return idx

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

    def __init__(
        self,
        parent=None,
        *,
        theme: ThemeSpec | None = None,
        icon_provider: IconProvider | None = None,
        edit_context: DelegateEditContext | None = None,
    ):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        self._icon_provider: IconProvider = icon_provider or StubIconProvider()
        self._edit_context: DelegateEditContext | None = edit_context
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
        # ``last_edit_result`` carries the post-commit decision (notably the
        # ``reopen_value_editor`` flag set by the host context) so callers can
        # consult an explicit ``EditResult`` instead of the private
        # ``_interactive`` backchannel.
        self.last_edit_result: EditResult | None = None
        self._active_type_edit_index: QPersistentModelIndex | None = None

    def set_edit_context(self, context: DelegateEditContext | None) -> None:
        self._edit_context = context

    @property
    def interactive(self) -> bool:
        """True while a user-driven type-combo commit is in flight.

        Stable, typed read of the otherwise-private ``_interactive``
        backchannel that ``JsonTab._on_type_changed`` consults to decide
        whether to auto-reopen the value editor.
        """
        return self._interactive

    def _context_for(self, host) -> DelegateEditContext:
        if self._edit_context is not None:
            return self._edit_context
        # No injected context — use the standalone fallback.  Parent crawling
        # was removed in Phase 1.2.
        ctx = DefaultEditContext()
        self._edit_context = ctx
        return ctx

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

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        source_index = self._source_index(index)
        if source_index.isValid() and self._is_active_type_edit_index(source_index):
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            paint_editor_underlay(painter, opt, option.widget)
            return
        super().paint(painter, option, index)

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
        for tp in USER_SELECTABLE_TYPES:
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
        # Pseudo text types (EMPTY_*, WS_*) collapse to their canonical parent
        # in the combobox so the user sees the type they could pick manually.
        current_type = canonical_text_type(item.json_type)
        idx = editor.findData(current_type)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        selected_type = editor.currentData()

        self._interactive = True
        try:
            ctx = self._context_for(editor)
            result = ctx.commit(index, selected_type, Qt.ItemDataRole.EditRole)
            self.last_edit_result = result
        finally:
            self._interactive = False
