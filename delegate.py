import base64
import gzip
import zlib
from datetime import time

from dateutil.parser import isoparse
from gmpy2 import mpq
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

import binary
from datetime_editor import DateTimeEditor
from enums import JsonType
from multiline_editor import MultilineDialog
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
                # Use a modal dialog-based editor for multiline text
                dlg = MultilineDialog(parent=parent, text=str(item.value or ""))
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    index.model().setData(index, dlg.text(), Qt.ItemDataRole.EditRole)
                # Do not return an inline editor for multiline values
                return None
            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                editor = QPlainTextEdit(parent)
                f = QFont()
                f.setCapitalization(QFont.Capitalization.AllUppercase)
                editor.setFont(f)
            case _:
                raise ValueError(f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}")

        return editor

    def setEditorData(
        self,
        editor: QBigIntSpinBox | QDoubleSpinBox | QComboBox | QLineEdit | QPlainTextEdit | QDateEdit | QDateTimeEdit,
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
            case JsonType.MULTILINE:
                editor: QPlainTextEdit
                editor.setPlainText(item.value)
            case JsonType.BYTES:
                editor: QPlainTextEdit
                raw = base64.b64decode(item.value, validate=True)
                formatted = binary.format_hex_dump(raw)
                editor.setPlainText(formatted)
            case JsonType.ZLIB:
                editor: QPlainTextEdit
                raw = base64.b64decode(item.value, validate=True)
                uncompressed = zlib.decompress(raw)
                formatted = binary.format_hex_dump(uncompressed)
                editor.setPlainText(formatted)
            case JsonType.GZIP:
                editor: QPlainTextEdit
                raw = base64.b64decode(item.value, validate=True)
                uncompressed = gzip.decompress(raw)
                formatted = binary.format_hex_dump(uncompressed)
                editor.setPlainText(formatted)
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
