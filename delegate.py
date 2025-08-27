import base64
import gzip
import zlib

from dateutil.parser import isoparse
from PySide6.QtCore import QAbstractItemModel, QDate, QDateTime, QModelIndex
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

import binary
from enums import JsonType
from qbigint_spinbox import QBigIntSpinBox
from qt2py import qtdatetime
from tree_item import JsonTreeItem


class ValueDelegate(QStyledItemDelegate):
    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QComboBox:

        item: JsonTreeItem = index.internalPointer()

        editor = None
        match item.json_type:
            case JsonType.INTEGER:
                editor = QBigIntSpinBox(parent)
            case JsonType.FLOAT:
                editor = QDoubleSpinBox(parent)
            case JsonType.PERCENT:
                editor = QDoubleSpinBox(
                    parent,
                    suffix="%",
                    decimals=1,
                    minimum=0,
                    maximum=100,
                    singleStep=0.1,
                )
            case JsonType.BOOLEAN:
                editor = QComboBox(parent)
                editor.addItem("true", True)
                editor.addItem("false", False)
            case JsonType.TEXT:
                editor = QLineEdit(parent)
            case JsonType.DATE:
                editor = QDateEdit(parent)
                editor.setDisplayFormat("yyyy-MM-dd")
            case JsonType.DATETIME | JsonType.DATETIMEZONE:
                editor = QDateTimeEdit(parent)
                editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")
            case JsonType.MULTI_LINE:
                editor = QPlainTextEdit(parent)
            case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
                editor = QPlainTextEdit(parent)
                f = QFont()
                f.setCapitalization(QFont.Capitalization.AllUppercase)
                editor.setFont(f)
            case unknown:
                raise ValueError(
                    f"Inappropriate `JsonType` in `ValueDelegate.createEditor()`: {item.json_type=}"
                )

        return editor

    def setEditorData(
        self,
        editor: (
            QBigIntSpinBox
            | QDoubleSpinBox
            | QComboBox
            | QLineEdit
            | QPlainTextEdit
            | QDateEdit
            | QDateTimeEdit
        ),
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
            case JsonType.TEXT:
                editor: QLineEdit
                editor.setText(item.value)
            case JsonType.DATE:
                editor: QDateEdit
                dt = isoparse(item.value)
                editor.setDate(QDate(dt.year, dt.month, dt.day))
            case JsonType.DATETIME:
                editor: QDateTimeEdit
                dt = isoparse(item.value)
                editor.setDateTime(
                    QDateTime(
                        dt.year,
                        dt.month,
                        dt.day,
                        dt.hour,
                        dt.minute,
                        dt.second,
                        dt.microsecond // 1000,
                    )
                )
            case JsonType.DATETIMEZONE:
                editor: QDateTimeEdit
                dt = isoparse(item.value)
                editor.setDateTime(qtdatetime(dt))
            case JsonType.MULTI_LINE:
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
                raise ValueError(
                    f"Inappropriate `JsonType` in `ValueDelegate.setEditorData()`: {item.json_type=}"
                )

    def setModelData(
        self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex
    ):
        pass
        # model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class JsonTypeDelegate(QStyledItemDelegate):
    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QComboBox:
        editor = QComboBox(parent)

        return editor

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        for tp in JsonType:
            editor.addItem(tp)

        editor.setCurrentText(next(iter(JsonType)))

    def setModelData(
        self, editor: QComboBox, model: QAbstractItemModel, index: QModelIndex
    ):
        pass
