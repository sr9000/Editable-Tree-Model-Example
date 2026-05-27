from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QTreeView

from tree.model_protocol import TreeModelLike
from tree.types import JsonType


def _row0_index(index: QModelIndex, model: TreeModelLike) -> QModelIndex:
    return model.index(index.row(), 0, index.parent()) if index.isValid() else QModelIndex()


def _move_row_between_parents(
    model: TreeModelLike, src_parent: QModelIndex, src_row: int, dst_parent: QModelIndex, dst_row: int
) -> bool:
    src_item = model.get_item(src_parent)
    dst_item = model.get_item(dst_parent)
    if not (0 <= src_row < src_item.child_count()):
        return False
    if not (0 <= dst_row <= dst_item.child_count()):
        return False
    if not model.beginMoveRows(src_parent, src_row, src_row, dst_parent, dst_row):
        return False
    moved = src_item.child_items.pop(src_row)
    dst_item.child_items.insert(dst_row, moved)
    moved.parent_item = dst_item
    src_item.mark_children_dirty()
    dst_item.mark_children_dirty()
    model.endMoveRows()
    return True


def action_insert_row_before(index: QModelIndex, model: TreeModelLike) -> bool:
    if not index.isValid():
        return model.insertRow(0, QModelIndex())
    row0 = _row0_index(index, model)
    return model.insertRow(row0.row(), row0.parent())


def action_insert_row_after(index: QModelIndex, model: TreeModelLike) -> bool:
    if not index.isValid():
        return model.insertRow(0, QModelIndex())
    row0 = _row0_index(index, model)
    return model.insertRow(row0.row() + 1, row0.parent())


def action_insert_row(index, model):
    # Backward-compatible alias used by existing call sites.
    return action_insert_row_after(index, model)


def action_insert_child(view: QTreeView, index: QModelIndex, model: TreeModelLike):
    index = model.index(index.row(), 0, index.parent())
    if not index.isValid():
        return False
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


def action_duplicate(view: QTreeView, index: QModelIndex, model: TreeModelLike) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid():
        return False
    item = model.get_item(row0)
    parent_index = row0.parent()
    insert_row = row0.row() + 1
    if not model.insertRow(insert_row, parent_index):
        return False
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


def action_move_up(view: QTreeView, index: QModelIndex, model: TreeModelLike) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid():
        return False
    parent = row0.parent()
    dst_parent = parent
    if row0.row() > 0:
        dst = row0.row() - 1
        if not model.move_row(parent, row0.row(), dst):
            return False
    else:
        parent_row0 = _row0_index(parent, model)
        if not parent_row0.isValid():
            return False
        if model.get_item(parent_row0) is model.root_item:
            return False
        dst_parent = parent_row0.parent()
        dst = parent_row0.row()
        if not _move_row_between_parents(model, parent, row0.row(), dst_parent, dst):
            return False
    view.selectionModel().setCurrentIndex(
        model.index(dst, 0, dst_parent),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    return True


def action_move_down(view: QTreeView, index: QModelIndex, model: TreeModelLike) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid():
        return False
    parent = row0.parent()
    if row0.row() < model.rowCount(parent) - 1:
        dst = row0.row() + 1
        dst_parent = parent
        if not model.move_row(parent, row0.row(), dst):
            return False
    else:
        parent_row0 = _row0_index(parent, model)
        if not parent_row0.isValid():
            return False
        if model.get_item(parent_row0) is model.root_item:
            return False
        dst_parent = parent_row0.parent()
        dst = parent_row0.row() + 1
        if not _move_row_between_parents(model, parent, row0.row(), dst_parent, dst):
            return False
    view.selectionModel().setCurrentIndex(
        model.index(dst, 0, dst_parent),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    return True


def action_sort_keys(index: QModelIndex, model: TreeModelLike, recursive: bool = False) -> bool:
    row0 = _row0_index(index, model)
    if not row0.isValid() and model.show_root:
        row0 = model.index(0, 0, QModelIndex())
    if not row0.isValid():
        return False
    return model.sort_keys(row0, recursive=recursive)
