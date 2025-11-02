from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtWidgets import QTreeView


def action_insert_row(index, model):
    return model.insertRow(index.row() + 1, index.parent())


def action_insert_child(view: QTreeView, index: QModelIndex, model):
    if model.columnCount(index) == 0:
        if not model.insertColumn(0, index):
            return False

    index = model.index(index.row(), 0, index.parent())

    if not model.insertRow(0, index):
        return False

    for column in range(model.columnCount(index)):
        child = model.index(0, column, index)
        model.setData(child, "[No data]", Qt.ItemDataRole.EditRole)
        if model.headerData(column, Qt.Orientation.Horizontal) is None:
            model.setHeaderData(
                column,
                Qt.Orientation.Horizontal,
                "[No header]",
                Qt.ItemDataRole.EditRole,
            )

    view.selectionModel().setCurrentIndex(model.index(0, 0, index), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    view.expand(model.index(0, 0, index))

    return True


def action_insert_column(index, model):
    column = index.column()
    changed = model.insertColumn(column + 1)

    if changed:
        model.setHeaderData(
            column + 1,
            Qt.Orientation.Horizontal,
            "[No header]",
            Qt.ItemDataRole.EditRole,
        )

    return changed
