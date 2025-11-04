import base64
import gzip
import zlib
from datetime import time

from dateutil.parser import isoparse
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

from datetime_editor import DateTimeEditor
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
                editor = QMpqSpinBox(parent)
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
                editor = DateTimeEditor(parent)
            case JsonType.MULTILINE:
                QMultilineDialog(  # Use a modal dialog-based editor for multiline text
                    parent=parent,
                    text=str(item.value or ""),
                    callback=lambda text: index.model().setData(index, text, Qt.ItemDataRole.EditRole) and None,
                ).open()

                return None  # Do not return an inline editor for multiline values

            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                QHexDialog(  # Use a modal dialog-based editor for binary data
                    parent=parent,
                    data=(decode_bytes(item.value, item.json_type)),
                    callback=lambda x: (
                        index.model().setData(index, encode_bytes(x, item.json_type), Qt.ItemDataRole.EditRole) and None
                    ),
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
                editor: QDoubleSpinBox
                editor.setValue(item.value)
            case JsonType.PERCENT:
                editor: QDoubleSpinBox
                editor.setValue(item.value * 100)
            case JsonType.BOOLEAN:
                editor: QComboBox
                editor.setCurrentIndex((not item.value) * 1)
            case JsonType.STRING:
                editor: QLineEdit
                editor.setText(item.value)
            case JsonType.TIME:
                editor: DateTimeEditor
                tm = time.fromisoformat(item.value)
                editor.setValue(tm)
            case JsonType.DATE:
                editor: DateTimeEditor
                dt = isoparse(item.value)
                editor.setValue(dt.date())
            case JsonType.DATETIME | JsonType.DATETIMEZONE:
                editor: DateTimeEditor
                dt = isoparse(item.value)
                editor.setValue(dt)
            case unknown:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.setEditorData()`: {item.json_type=}")

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, index: QModelIndex):
        pass
        # model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class JsonTypeDelegate(QStyledItemDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        return QComboBox(parent)

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        for tp in JsonType:
            editor.addItem(tp)

        editor.setCurrentText(next(iter(JsonType)))

    def setModelData(self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex):
        pass


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
