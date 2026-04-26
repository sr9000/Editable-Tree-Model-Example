from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QTreeView

from enums import JsonType


def _row0_index(index: QModelIndex, model) -> QModelIndex:
    return model.index(index.row(), 0, index.parent()) if index.isValid() else QModelIndex()


def action_insert_row_before(index: QModelIndex, model) -> bool:
    if not index.isValid():
        return model.insertRow(0, QModelIndex())
    row0 = _row0_index(index, model)
    return model.insertRow(row0.row(), row0.parent())


def action_insert_row_after(index: QModelIndex, model) -> bool:
    if not index.isValid():
        return model.insertRow(0, QModelIndex())
    row0 = _row0_index(index, model)
    return model.insertRow(row0.row() + 1, row0.parent())


def action_insert_row(index, model):
    # Backward-compatible alias used by existing call sites.
    return action_insert_row_after(index, model)


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


def _copy_name(base: str, used: set[str]) -> str:
    candidate = f"{base}_copy"
    if candidate not in used:
        return candidate
    i = 2
    while f"{candidate}_{i}" in used:
        i += 1
    return f"{candidate}_{i}"


def action_duplicate(view: QTreeView, index: QModelIndex, model) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid() or not hasattr(model, "get_item"):
        return False

    item = model.get_item(row0)
    parent_index = row0.parent()
    insert_row = row0.row() + 1
    if not model.insertRow(insert_row, parent_index):
        return False

    # Copy key name only under OBJECT parents and resolve collisions.
    parent_item = model.get_item(parent_index)
    if parent_item.json_type is JsonType.OBJECT and isinstance(item.name, str):
        used = {c.name for i, c in enumerate(parent_item.child_items) if i != insert_row and isinstance(c.name, str)}
        new_name = item.name if item.name not in used else _copy_name(item.name, used)
        model.setData(model.index(insert_row, 0, parent_index), new_name)

    value_index = model.index(insert_row, 2, parent_index)
    if not model.setData(value_index, item.to_json()):
        model.removeRow(insert_row, parent_index)
        return False

    view.selectionModel().setCurrentIndex(
        model.index(insert_row, 0, parent_index),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    return True


def action_move_up(view: QTreeView, index: QModelIndex, model) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid() or row0.row() <= 0 or not hasattr(model, "move_row"):
        return False

    dst = row0.row() - 1
    if not model.move_row(row0.parent(), row0.row(), dst):
        return False

    view.selectionModel().setCurrentIndex(
        model.index(dst, 0, row0.parent()),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    return True


def action_move_down(view: QTreeView, index: QModelIndex, model) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid() or not hasattr(model, "move_row"):
        return False

    parent = row0.parent()
    if row0.row() >= model.rowCount(parent) - 1:
        return False

    dst = row0.row() + 1
    if not model.move_row(parent, row0.row(), dst):
        return False

    view.selectionModel().setCurrentIndex(
        model.index(dst, 0, parent),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    return True


def action_sort_keys(index: QModelIndex, model, recursive: bool = False) -> bool:
    row0 = _row0_index(index, model)
    if not hasattr(model, "sort_keys"):
        return False
    if not row0.isValid() and getattr(model, "show_root", False):
        row0 = model.index(0, 0, QModelIndex())
    if not row0.isValid():
        return False
    return model.sort_keys(row0, recursive=recursive)
