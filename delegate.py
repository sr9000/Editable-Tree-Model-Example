from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QWidget,
)


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
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
