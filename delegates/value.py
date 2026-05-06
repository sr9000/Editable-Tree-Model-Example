import binascii
import zlib

from gmpy2 import mpq
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QStyle, QStyleOptionViewItem, QWidget

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from delegates.base import _CapsLockSafeLineEdit, _TextEditorDelegateBase
from delegates.bytes_codec import decode_bytes, encode_bytes
from delegates.value_formatting import _apply_type_style, format_default, format_with_type
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from themes import LIGHT_DEFAULT
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model_roles import JSON_TYPE_ROLE
from tree.types import JsonType


class ValueDelegate(_TextEditorDelegateBase):
    def __init__(self, parent=None, *, theme: ThemeSpec | None = None):
        super().__init__(parent)
        self._theme = theme or LIGHT_DEFAULT

    def set_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme

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
    def _format_with_type(value, json_type: JsonType | None) -> str:
        return format_with_type(value, json_type)

    def displayText(self, value, locale):  # type: ignore[override]
        return self._format_default(value)

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        model = index.model()
        raw = model.data(index, Qt.ItemDataRole.EditRole) if model is not None else index.data(Qt.ItemDataRole.EditRole)
        json_type = model.data(index, JSON_TYPE_ROLE) if model is not None else index.data(JSON_TYPE_ROLE)
        typed = json_type if isinstance(json_type, JsonType) else None
        option.text = self._format_with_type(raw, typed)
        if typed is not None:
            _apply_type_style(
                option,
                self._theme.types[typed],
                selected=bool(option.state & QStyle.StateFlag.State_Selected),
                allow_background=True,
            )

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
