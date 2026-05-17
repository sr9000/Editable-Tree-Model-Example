import binascii
import zlib

from gmpy2 import mpq
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QColorDialog, QComboBox, QLineEdit, QStyle, QStyleOptionViewItem, QTreeView, QWidget

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from delegates.base import _CapsLockSafeLineEdit, _TextEditorDelegateBase
from delegates.bytes_codec import decode_bytes, encode_bytes
from delegates.color_codec import color_to_html, parse_color
from delegates.validation_badge import draw_severity_badge
from delegates.value_formatting import _apply_type_style, format_default, format_with_type
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from themes import LIGHT_DEFAULT
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model_roles import JSON_TYPE_ROLE, VALIDATION_SEVERITY_ROLE
from tree.types import JsonType


class ValueDelegate(_TextEditorDelegateBase):
    def __init__(self, parent=None, *, theme: ThemeSpec | None = None):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT
        self._monospace_fields_enabled = False
        self._mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()

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

    @staticmethod
    def _find_tab(host) -> object | None:
        cursor = host
        while cursor is not None:
            if hasattr(cursor, "commit_set_data"):
                return cursor
            cursor = cursor.parent() if hasattr(cursor, "parent") else None
        return None

    @staticmethod
    def _commit(
        index: QModelIndex | QPersistentModelIndex,
        value,
        role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole,
        host=None,
    ) -> bool:
        idx = ValueDelegate._to_index(index)
        model = idx.model()
        if model is None:
            return False

        tab = ValueDelegate._find_tab(host)
        if tab is not None:
            return bool(tab.commit_set_data(idx, value, role))
        return bool(model.setData(idx, value, role))

    @staticmethod
    def _notify_status(host, message: str, timeout: int = 3000) -> None:
        """Surface a transient status message via the owning tab's status callback, if available."""
        tab = ValueDelegate._find_tab(host)
        cb = getattr(tab, "_status_message_callback", None) if tab is not None else None
        if cb is not None:
            try:
                cb(message, timeout)
            except Exception:
                pass

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget | None:
        source_index = self._source_index(index)
        item: JsonTreeItem = source_index.internalPointer()

        editor = None
        match item.json_type:
            case JsonType.INTEGER:
                editor = QBigIntSpinBox(parent)
            case JsonType.FLOAT:
                editor = QMpqSpinBox(parent, item.value)
            case JsonType.PERCENT:
                editor = QMpqSpinBox(
                    parent,
                    suffix="%",
                    minimum=mpq("0"),
                    maximum=mpq("100"),
                    single_step=mpq("0.1"),
                )
            case JsonType.BOOLEAN:
                editor = QComboBox(parent)
                editor.addItem("true", True)
                editor.addItem("false", False)
            case JsonType.STRING | JsonType.UNICODE:
                editor = _CapsLockSafeLineEdit(parent)
            case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE:
                editor = BetterDateTimeEditor(parent)
            case JsonType.MULTILINE | JsonType.TEXT:
                pidx = QPersistentModelIndex(index)

                def _save_multiline(text: str) -> None:
                    if pidx.isValid():
                        self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                QMultilineDialog(parent=parent, text=str(item.value or ""), callback=_save_multiline).open()
                return None

            case JsonType.COLOR_RGB | JsonType.COLOR_RGBA:
                pidx = QPersistentModelIndex(index)
                initial = parse_color(item.value if isinstance(item.value, str) else "") or parse_color("#000000")

                dialog = QColorDialog(initial, parent)
                if item.json_type is JsonType.COLOR_RGBA:
                    dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
                dialog.setWindowTitle(
                    "Pick color (RGBA)" if item.json_type is JsonType.COLOR_RGBA else "Pick color (RGB)"
                )

                target_type = item.json_type

                def _on_color_selected(selected) -> None:
                    if not pidx.isValid():
                        return
                    text = color_to_html(selected, target_type)
                    self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                dialog.colorSelected.connect(_on_color_selected)
                dialog.open()
                return None

            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                try:
                    decoded = decode_bytes(item.value, item.json_type)
                except (ValueError, OSError, zlib.error, binascii.Error) as exc:
                    self._notify_status(parent, f"Decode failed: {exc}", 4000)
                    return None

                pidx = QPersistentModelIndex(index)

                def _save_binary(data: bytes) -> None:
                    if not pidx.isValid():
                        return
                    encoded = encode_bytes(data, item.json_type)
                    self._commit(pidx, encoded, Qt.ItemDataRole.EditRole, host=parent)

                QHexDialog(parent=parent, data=decoded, callback=_save_binary).open()
                return None

            case _:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}")

        if editor is not None:
            editor.setFont(self._apply_monospace_font(editor.font()))
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        source_index = self._source_index(index)
        item: JsonTreeItem = source_index.internalPointer()
        value = item.value

        if isinstance(editor, QBigIntSpinBox):
            try:
                editor.setValue(int(value))
            except (TypeError, ValueError):
                editor.setValue(0)
            return

        if isinstance(editor, QMpqSpinBox):
            try:
                v = mpq(str(value)) if not isinstance(value, mpq) else value
            except (TypeError, ValueError):
                v = mpq(0)
            if item.json_type is JsonType.PERCENT:
                v = v * 100
            editor.setValue(v)
            return

        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(0 if bool(value) else 1)
            return

        if isinstance(editor, BetterDateTimeEditor):
            category = self._category_for_json_type(item.json_type)
            if category is not None:
                editor.setCategory(category)
            editor.setText(str(value or ""))
            return

        if isinstance(editor, QLineEdit):
            editor.setText("" if value is None else str(value))
            return

        super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        if isinstance(editor, QBigIntSpinBox):
            self._commit(index, editor.value(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QMpqSpinBox):
            source_index = self._source_index(index)
            item: JsonTreeItem = source_index.internalPointer()
            value = editor.value()
            if item is not None and item.json_type is JsonType.PERCENT:
                value = value / mpq("100")
            self._commit(index, value, Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QComboBox):
            self._commit(index, editor.currentData(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, BetterDateTimeEditor):
            self._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QLineEdit):
            self._commit(index, editor.text(), Qt.ItemDataRole.EditRole, host=editor)
            return

        super().setModelData(editor, model, index)

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
            case _:
                return None
