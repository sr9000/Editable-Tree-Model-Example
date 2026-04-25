from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QTreeView

from enums import JsonType


def action_insert_row(index, model):
    return model.insertRow(index.row() + 1, index.parent())


def action_insert_child(view: QTreeView, index: QModelIndex, model):
    index = model.index(index.row(), 0, index.parent())
    if not index.isValid():
        return False

    if hasattr(model, "get_item"):
        parent_item = model.get_item(index)
        if parent_item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
            return False

    if not model.insertRow(0, index):
        return False

    view.selectionModel().setCurrentIndex(model.index(0, 0, index), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    view.expand(model.index(0, 0, index))

    return True
