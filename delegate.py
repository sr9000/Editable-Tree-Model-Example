import base64
import gzip
import zlib

from gmpy2 import mpq
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QLineEdit,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from datetime_editor.better_dt_editor import BetterDateTimeEditor
from datetime_editor.enums import DateTimeCategory
from dialogs.qhexedit_dlg import QHexDialog
from dialogs.qmultiline_dlg import QMultilineDialog
from enums import JsonType
from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from tree_item import JsonTreeItem


class ValueDelegate(QStyledItemDelegate):
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
            case JsonType.STRING:
                editor = QLineEdit(parent)
            case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE:
                editor = BetterDateTimeEditor(parent)
            case JsonType.MULTILINE:
                def _save_multiline(text: str) -> None:
                    index.model().setData(index, text, Qt.ItemDataRole.EditRole)

                QMultilineDialog(  # Use a modal dialog-based editor for multiline text
                    parent=parent,
                    text=str(item.value or ""),
                    callback=_save_multiline,
                ).open()

                return None  # Do not return an inline editor for multiline values

            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                def _save_binary(data: bytes) -> None:
                    encoded = encode_bytes(data, item.json_type)
                    index.model().setData(index, encoded, Qt.ItemDataRole.EditRole)

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
        editor: QBigIntSpinBox | QDoubleSpinBox | QComboBox | QLineEdit | QDateEdit | QDateTimeEdit,
        index: QModelIndex,
    ):
        item: JsonTreeItem = index.internalPointer()

        match item.json_type:
            case JsonType.INTEGER:
                editor: QBigIntSpinBox
                editor.setValue(item.value)
            case JsonType.FLOAT:
                # QMpqSpinBox preserves mpq, set directly
                sb: QMpqSpinBox = editor  # type: ignore[assignment]
                sb.setValue(item.value)
            case JsonType.PERCENT:
                # Stored as fraction 0..1, editor shows 0..100 with "%"
                sb: QMpqSpinBox = editor  # type: ignore[assignment]
                sb.setValue(item.value * 100)
            case JsonType.BOOLEAN:
                editor: QComboBox
                editor.setCurrentIndex((not item.value) * 1)
            case JsonType.STRING:
                editor: QLineEdit
                editor.setText(item.value)
            case JsonType.TIME | JsonType.DATE | JsonType.DATETIME | JsonType.DATETIMEZONE:
                dt_editor: BetterDateTimeEditor = editor  # type: ignore[assignment]
                dt_editor.setCategory(self._category_for_json_type(item.json_type))
                dt_editor.setText(str(item.value or ""))
            case unknown:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.setEditorData()`: {item.json_type=}")

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        item: JsonTreeItem = index.internalPointer()

        match item.json_type:
            case JsonType.INTEGER:
                sb: QBigIntSpinBox = editor  # type: ignore[assignment]
                model.setData(index, sb.value(), Qt.ItemDataRole.EditRole)
            case JsonType.FLOAT:
                sb: QMpqSpinBox = editor  # type: ignore[assignment]
                model.setData(index, sb.value(), Qt.ItemDataRole.EditRole)
            case JsonType.PERCENT:
                sb: QMpqSpinBox = editor  # type: ignore[assignment]
                model.setData(index, sb.value() / mpq("100"), Qt.ItemDataRole.EditRole)
            case JsonType.BOOLEAN:
                cb: QComboBox = editor  # type: ignore[assignment]
                model.setData(index, cb.currentData(), Qt.ItemDataRole.EditRole)
            case JsonType.STRING:
                le: QLineEdit = editor  # type: ignore[assignment]
                model.setData(index, le.text(), Qt.ItemDataRole.EditRole)
            case JsonType.TIME | JsonType.DATE | JsonType.DATETIME | JsonType.DATETIMEZONE:
                dt_editor: BetterDateTimeEditor = editor  # type: ignore[assignment]
                # Keep exactly what user typed; DateTimeEditor ensures validity
                model.setData(index, dt_editor.text(), Qt.ItemDataRole.EditRole)
            case JsonType.MULTILINE | JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                # Handled via modal dialogs, nothing to do here
                return
            case _:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.setModelData()`: {item.json_type=}")

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
