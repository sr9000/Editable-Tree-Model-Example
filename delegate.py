from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from enums import JsonType


class ComboBoxDelegate(QStyledItemDelegate):
    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QComboBox:
        editor = QComboBox(parent)
        editor.setEditable(True)

        return editor

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        value = index.data(Qt.ItemDataRole.EditRole)

        no_data = "[No data]"
        if value is None:
            editor.setCurrentText(no_data)
            editor.addItem(no_data)
        else:
            editor.setCurrentText(value)
            editor.addItem(value)

            if value != no_data:
                editor.addItem(no_data)

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
