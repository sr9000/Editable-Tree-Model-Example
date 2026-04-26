import base64
import gzip
import zlib

from gmpy2 import mpq
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from enums import JsonType
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from tree_item import JsonTreeItem


class ValueDelegate(QStyledItemDelegate):
    @staticmethod
    def _to_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index

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

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget | None:

        item: JsonTreeItem = index.internalPointer()

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
                editor = QLineEdit(parent)
            case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE:
                editor = BetterDateTimeEditor(parent)
            case JsonType.MULTILINE | JsonType.TEXT:
                pidx = QPersistentModelIndex(index)

                def _save_multiline(text: str) -> None:
                    if pidx.isValid():
                        self._commit(pidx, text, Qt.ItemDataRole.EditRole, host=parent)

                QMultilineDialog(  # Use a modal dialog-based editor for multiline text
                    parent=parent,
                    text=str(item.value or ""),
                    callback=_save_multiline,
                ).open()

                return None  # Do not return an inline editor for multiline values

            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                pidx = QPersistentModelIndex(index)

                def _save_binary(data: bytes) -> None:
                    if not pidx.isValid():
                        return
                    encoded = encode_bytes(data, item.json_type)
                    self._commit(pidx, encoded, Qt.ItemDataRole.EditRole, host=parent)

                QHexDialog(  # Use a modal dialog-based editor for binary data
                    parent=parent,
                    data=(decode_bytes(item.value, item.json_type)),
                    callback=_save_binary,
                ).open()

                return None  # Do not return an inline editor for binary values

            case _:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}")

        return editor

    def setEditorData(
        self,
        editor: QWidget,
        index: QModelIndex,
    ):
        # IMPORTANT: dispatch on the editor's *widget class*, not on
        # ``item.json_type``. The editor was created for a specific JSON
        # type by ``createEditor``; if the type was changed afterwards
        # (e.g. via the type combo) Qt may still call us with that old
        # widget. Keying off ``item.json_type`` would then call methods
        # that don't exist on the old widget (``setText`` on
        # ``QMpqSpinBox`` etc.).
        item: JsonTreeItem = index.internalPointer()
        value = item.value

        if isinstance(editor, QBigIntSpinBox):
            try:
                editor.setValue(int(value))
            except (TypeError, ValueError):
                editor.setValue(0)
            return

        if isinstance(editor, QMpqSpinBox):
            # PERCENT stores 0..1 fractions but the editor shows 0..100.
            try:
                v = mpq(str(value)) if not isinstance(value, mpq) else value
            except (TypeError, ValueError):
                v = mpq(0)
            if item.json_type is JsonType.PERCENT:
                v = v * 100
            editor.setValue(v)
            return

        if isinstance(editor, QComboBox):
            # Used for BOOLEAN values.
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

        # Unknown editor class — fall back to the default implementation.
        super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        # Same rationale as in setEditorData: dispatch by editor widget
        # class so a stale editor (created for a previous JSON type) still
        # commits a sensible value. The model's ``setData`` handles type
        # coercion or rejection.
        if isinstance(editor, QBigIntSpinBox):
            self._commit(index, editor.value(), Qt.ItemDataRole.EditRole, host=editor)
            return

        if isinstance(editor, QMpqSpinBox):
            item: JsonTreeItem = index.internalPointer()
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

        # Modal-dialog types have no inline editor; nothing to commit.
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


class JsonTypeDelegate(QStyledItemDelegate):
    @staticmethod
    def _find_tab(host) -> object | None:
        cursor = host
        while cursor is not None:
            if hasattr(cursor, "commit_set_data"):
                return cursor
            cursor = cursor.parent() if hasattr(cursor, "parent") else None
        return None

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        editor = QComboBox(parent)
        for tp in JsonType:
            editor.addItem(tp.value, tp)
        return editor

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        item: JsonTreeItem = index.internalPointer()
        idx = editor.findData(item.json_type)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        selected_type = editor.currentData()

        tab = self._find_tab(editor)
        if tab is not None:
            tab.commit_set_data(index, selected_type, Qt.ItemDataRole.EditRole)
            return

        model.setData(index, selected_type, Qt.ItemDataRole.EditRole)


def decode_bytes(b64string: str, json_type: JsonType) -> bytes:
    # Prepare binary data for hex editor
    raw = base64.b64decode(b64string, validate=True) if b64string else b""

    match json_type:  # Decompress if needed
        case JsonType.ZLIB:
            return zlib.decompress(raw)
        case JsonType.GZIP:
            return gzip.decompress(raw)
        case _:
            return raw


# Callback to handle edited data
def encode_bytes(edited_data: bytes, json_type: JsonType) -> str:
    match json_type:  # Compress if needed
        case JsonType.ZLIB:
            edited_data = zlib.compress(edited_data)
        case JsonType.GZIP:
            edited_data = gzip.compress(edited_data)

    # Encode to base64 and update model
    return base64.b64encode(edited_data).decode("ascii")
