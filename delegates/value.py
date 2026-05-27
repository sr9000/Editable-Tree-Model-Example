from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMessageBox, QStyle, QStyleOptionViewItem, QTreeView, QWidget

from datetime_editor.enums import DateTimeCategory
from delegates.base import _TextEditorDelegateBase, paint_editor_underlay
from delegates.color_codec import parse_color
from delegates.edit_context import DefaultEditContext, DelegateEditContext
from state.edit_limits import (
    get_multiline_edit_warning_limit_chars,
    get_string_edit_warning_limit_chars,
)
from delegates.editor_factory import (
    _SecretEditorWatcher,
    create_value_editor,
    set_value_editor_data,
    set_value_model_data,
)
from delegates.validation_badge import draw_severity_badge
from delegates.value_formatting import _apply_type_style, format_default, format_with_type
from themes import LIGHT_DEFAULT
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model_roles import JSON_TYPE_ROLE, VALIDATION_SEVERITY_ROLE
from tree.types import JsonType


def _tab_adapter_context(host) -> DelegateEditContext:
    """No-op fallback retained as a hard-error breadcrumb.

    Phase 1.2 deletes parent-crawling and wires an explicit context from
    ``documents/tab_setup.py``.  Reaching this fallback means the delegate
    was instantiated without an ``edit_context`` and outside of a host that
    provides one, so the safest behaviour is the bare model fallback.
    """
    return DefaultEditContext()


class ValueDelegate(_TextEditorDelegateBase):
    def __init__(
        self,
        parent=None,
        *,
        theme: ThemeSpec | None = None,
        edit_context: DelegateEditContext | None = None,
    ):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        self._monospace_fields_enabled = False
        self._mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self._secret_watchers: dict[QWidget, _SecretEditorWatcher] = {}
        self._edit_context: DelegateEditContext | None = edit_context

    # ----- edit-context plumbing -----
    def set_edit_context(self, context: DelegateEditContext | None) -> None:
        self._edit_context = context

    def _context_for(self, host) -> DelegateEditContext:
        if self._edit_context is not None:
            return self._edit_context
        # Transitional: until Phase 1.2 wires an explicit context, derive one
        # from the host widget hierarchy.  Once tab_setup injects a context,
        # this fallback is never reached.
        return _tab_adapter_context(host)

    def set_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        self._monospace_fields_enabled = bool(enabled)

    def set_monospace_font_family(self, family: str) -> None:
        if family:
            self._mono_family = str(family)

    def _apply_monospace_font(self, font: QFont) -> QFont:
        if not self._monospace_fields_enabled:
            return font
        f = QFont(font)
        f.setFamily(self._mono_family)
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setFixedPitch(True)
        return f

    @staticmethod
    def _source_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        idx = ValueDelegate._to_index(index)
        model = idx.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(idx)
        return idx

    @staticmethod
    def _format_default(value) -> str:
        return format_default(value)

    @staticmethod
    def _format_with_type(
        value,
        json_type: JsonType | None,
        *,
        item: JsonTreeItem | None = None,
        show_preview: bool = True,
    ) -> str:
        return format_with_type(value, json_type, item=item, show_preview=show_preview)

    @staticmethod
    def _coerce_json_type(value) -> JsonType | None:
        if isinstance(value, JsonType):
            return value
        if isinstance(value, str):
            try:
                return JsonType(value)
            except ValueError:
                return None
        return None

    def displayText(self, value, locale):  # type: ignore[override]
        return self._format_default(value)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        source_index = self._source_index(index)
        item = source_index.internalPointer() if source_index.isValid() else None
        # Read raw value and type directly from the tree item when possible.
        # This avoids the Qt QVariant round-trip that silently overflows for
        # arbitrarily-large Python integers (bigints > 8-byte signed int limit).
        if isinstance(item, JsonTreeItem):
            raw = item.data(source_index.column())
            json_type = item.json_type
        else:
            model = index.model()
            raw = (
                model.data(index, Qt.ItemDataRole.EditRole)
                if model is not None
                else index.data(Qt.ItemDataRole.EditRole)
            )
            json_type = model.data(index, JSON_TYPE_ROLE) if model is not None else index.data(JSON_TYPE_ROLE)
        typed = self._coerce_json_type(json_type)
        show_preview = True
        if typed in (JsonType.ARRAY, JsonType.OBJECT) and isinstance(option.widget, QTreeView):
            tree_index = index.siblingAtColumn(0)
            show_preview = not option.widget.isExpanded(tree_index)
        option.text = self._format_with_type(
            raw,
            typed,
            item=item if isinstance(item, JsonTreeItem) else None,
            show_preview=show_preview,
        )
        if typed in (JsonType.COLOR_RGB, JsonType.COLOR_RGBA) and isinstance(raw, str):
            swatch = self._color_swatch_icon(raw, option)
            if swatch is not None:
                option.icon = swatch
                option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration
        if typed is not None:
            _apply_type_style(
                option,
                self._theme.types[typed],
                selected=bool(option.state & QStyle.StateFlag.State_Selected),
                allow_background=True,
            )
        option.font = self._apply_monospace_font(option.font)

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        if self._is_editor_open(index):
            idx = self._to_index(index)
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, idx)
            paint_editor_underlay(painter, opt, option.widget)
            return
        severity = index.data(VALIDATION_SEVERITY_ROLE)
        if severity is not None:
            idx = self._to_index(index)
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, idx)
            draw_severity_badge(painter, opt, severity, self._theme)
            return
        super().paint(painter, option, index)

    @staticmethod
    def _color_swatch_icon(value: str, option: QStyleOptionViewItem) -> QIcon | None:
        color = parse_color(value)
        if color is None:
            return None
        size = max(8, min(option.decorationSize.height() or 16, 32))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            # Checkerboard for transparency awareness
            if color.alpha() < 255:
                step = max(2, size // 4)
                light = Qt.GlobalColor.white
                dark = Qt.GlobalColor.lightGray
                for y in range(0, size, step):
                    for x in range(0, size, step):
                        painter.fillRect(x, y, step, step, light if ((x // step + y // step) % 2 == 0) else dark)
            painter.fillRect(0, 0, size, size, color)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawRect(0, 0, size - 1, size - 1)
        finally:
            painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _to_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if isinstance(index, QPersistentModelIndex):
            return QModelIndex(index)
        return index

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget | None:
        return create_value_editor(self, parent, option, index)

    def _finalize_secret_editor(self, editor: QWidget, index: QPersistentModelIndex) -> None:
        if editor is None or not index.isValid():
            return
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, self.EndEditHint.NoHint)

    def destroyEditor(self, editor, index) -> None:  # type: ignore[override]
        watcher = self._secret_watchers.pop(editor, None)
        if watcher is not None:
            watcher.cleanup()
        super().destroyEditor(editor, index)

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        set_value_editor_data(self, editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        set_value_model_data(self, editor, model, index)

    @staticmethod
    def _category_for_json_type(json_type: JsonType) -> DateTimeCategory | None:
        match json_type:
            case JsonType.TIME:
                return DateTimeCategory.Time
            case JsonType.DATE:
                return DateTimeCategory.Date
            case JsonType.DATETIME:
                return DateTimeCategory.DateTime
            case JsonType.DATETIMEZONE:
                return DateTimeCategory.DateTimeWithTZ
            case JsonType.DATETIMEUTC:
                return DateTimeCategory.DateTimeUTC
            case _:
                return None
