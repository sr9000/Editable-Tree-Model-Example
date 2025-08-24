import base64
import gzip
import zlib

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QDate,
    QDateTime,
    QTime,
    QTimeZone,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
    QDoubleSpinBox,
    QDateEdit,
    QDateTimeEdit,
)
from dateutil.parser import isoparse

import binary
from enums import JsonType
from tree_item import JsonTreeItem


class ValueDelegate(QStyledItemDelegate):
    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QComboBox:

        item: JsonTreeItem = index.internalPointer()

        editor = None
        match item.json_type:
            case JsonType.INTEGER:
                editor = QSpinBox(parent)
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
                editor.addItem("false", False)
                editor.addItem("true", True)
            case JsonType.SINGLE_LINE:
                editor = QLineEdit(parent)
            case JsonType.DATE:
                editor = QDateEdit(parent)
            case JsonType.DATETIME, JsonType.DATETIMEZONE:
                editor = QDateTimeEdit(parent)
            case JsonType.MULTI_LINE:
                editor = QPlainTextEdit(parent)
            case JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP:
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
            QSpinBox
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
                editor: QSpinBox
                editor.setValue(item.value)
            case JsonType.FLOAT:
                editor: QDoubleSpinBox
                editor.setValue(item.value)
            case JsonType.PERCENT:
                editor: QDoubleSpinBox
                editor.setValue(item.value * 100)
            case JsonType.BOOLEAN:
                editor: QComboBox
                editor.setCurrentIndex(item.value * 1)
            case JsonType.SINGLE_LINE:
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
                        dt.microsecond,
                    )
                )
            case JsonType.DATETIMEZONE:
                editor: QDateTimeEdit
                dt = isoparse(item.value)
                editor.setDateTime(
                    QDateTime(
                        QDate(dt.year, dt.month, dt.day),
                        QTime(dt.hour, dt.minute, dt.second, dt.microsecond),
                        QTimeZone(int(dt.utcoffset().total_seconds())),
                    )
                )
            case JsonType.MULTI_LINE:
                editor: QPlainTextEdit
                editor.setPlainText(item.value)
            case JsonType.BYTES:
                editor: QPlainTextEdit
                raw = base64.b64decode(item.value)
                formatted = binary.format_hex_dump(raw)
                editor.setPlainText(formatted)
            case JsonType.ZLIB:
                editor: QPlainTextEdit
                raw = base64.b64decode(item.value)
                uncompressed = zlib.decompress(raw)
                formatted = binary.format_hex_dump(uncompressed)
                editor.setPlainText(formatted)
            case JsonType.GZIP:
                editor: QPlainTextEdit
                raw = base64.b64decode(item.value)
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
