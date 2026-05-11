from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QTreeView

from model_actions import (
    _copy_name,
    action_duplicate,
    action_insert_child,
    action_insert_row_after,
    action_insert_row_before,
    action_move_down,
    action_move_up,
    action_sort_keys,
)
from tree.types import JsonType
from tree_actions.clipboard import copy_selection
from tree_actions.selection import (
    _index_path,
    _is_root_index,
    _resolve_model,
    _row0,
    selection_spans_multiple_parents,
    _to_source_index,
    _to_view_index,
    top_level_source_rows as _top_level_selected_rows,
)


def _tab_of(tree_view: QTreeView):
    parent = tree_view.parent()
    if parent is not None and hasattr(parent, "push_insert_rows"):
        return parent
    return None


def insert_sibling_before(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    tab = _tab_of(tree_view)
    if tab is not None:
        if not current.isValid():
            parent_index = QModelIndex()
            row = 0
        else:
            row0 = _row0(model, current)
            if _is_root_index(model, row0):
                return False
            parent_index = row0.parent()
            row = row0.row()
        parent_item = model.get_item(parent_index)
        name = parent_item._unique_child_name() if parent_item.json_type is JsonType.OBJECT else None
        return tab.push_insert_rows(
            [
                {
                    "parent_path": tab._index_path(parent_index),
                    "row": row,
                    "value": None,
                    "name": name,
                }
            ],
            label="insert sibling before",
        )

    return action_insert_row_before(current, model)


def insert_sibling_after(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    tab = _tab_of(tree_view)
    if tab is not None:
        if not current.isValid():
            parent_index = QModelIndex()
            row = 0
        else:
            row0 = _row0(model, current)
            if _is_root_index(model, row0):
                return False
            parent_index = row0.parent()
            row = row0.row() + 1
        parent_item = model.get_item(parent_index)
        name = parent_item._unique_child_name() if parent_item.json_type is JsonType.OBJECT else None
        return tab.push_insert_rows(
            [
                {
                    "parent_path": tab._index_path(parent_index),
                    "row": row,
                    "value": None,
                    "name": name,
                }
            ],
            label="insert sibling after",
        )

    return action_insert_row_after(current, model)


def insert_child_current(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if not current.isValid():
        return False

    parent_row0 = _row0(model, current)
    parent_item = model.get_item(parent_row0)
    if parent_item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
        return False

    tab = _tab_of(tree_view)
    if tab is not None:
        name = parent_item._unique_child_name() if parent_item.json_type is JsonType.OBJECT else None
        ok = tab.push_insert_rows(
            [
                {
                    "parent_path": tab._index_path(parent_row0),
                    "row": 0,
                    "value": None,
                    "name": name,
                }
            ],
            label="insert child",
        )
        if ok:
            tree_view.expand(_to_view_index(tree_view, parent_row0))
        return ok

    return action_insert_child(tree_view, current, model)


def delete_selection(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    rows = [idx for idx in _top_level_selected_rows(tree_view) if not _is_root_index(model, idx)]
    if not rows:
        return False

    tab = _tab_of(tree_view)
    if tab is not None:
        return tab.push_remove_rows(rows, label="delete")

    rows = sorted(rows, key=lambda idx: (_index_path(idx.parent()), idx.row()), reverse=True)
    changed = False
    for idx in rows:
        changed = model.removeRow(idx.row(), idx.parent()) or changed
    return changed


def cut_selection(tree_view: QTreeView) -> bool:
    if not copy_selection(tree_view):
        return False
    return delete_selection(tree_view)


def duplicate_selection(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    rows = [idx for idx in _top_level_selected_rows(tree_view) if not _is_root_index(model, idx)]
    if not rows:
        return False

    ordered = sorted(rows, key=_index_path, reverse=True)

    tab = _tab_of(tree_view)
    if tab is not None:
        inserts: list[dict] = []
        first_source_qname: str | None = None
        for idx in ordered:
            row0 = _row0(model, idx)
            item = model.get_item(row0)
            parent_index = row0.parent()
            parent_item = model.get_item(parent_index)
            insert_row = row0.row() + 1
            name: str | None = None
            if parent_item.json_type is JsonType.OBJECT and isinstance(item.name, str):
                used = {c.name for c in parent_item.child_items if isinstance(c.name, str)}
                name = _copy_name(item.name, used)
            inserts.append(
                {
                    "parent_path": tab._index_path(parent_index),
                    "row": insert_row,
                    "value": item.to_json(),
                    "name": name,
                }
            )
            if first_source_qname is None:
                first_source_qname = tab._qualified_name(row0)
        return tab.push_insert_rows(inserts, label="duplicate", target_qname=first_source_qname)

    changed = False
    for idx in ordered:
        changed = action_duplicate(tree_view, idx, model) or changed
    return changed


def _ordered_non_root_rows(tree_view: QTreeView):
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return None, []
    rows = [idx for idx in _top_level_selected_rows(tree_view) if idx.isValid() and not _is_root_index(model, idx)]
    return model, sorted(rows, key=_index_path)


def _status_partial_move(tab) -> None:
    callback = getattr(tab, "_status_message_callback", None)
    if callback is not None:
        callback("Moved part of the selection", 2000)


def _move_same_parent(tab, model, rows: list, *, up: bool) -> bool:
    parent = rows[0].parent()
    ordered = sorted((_row0(model, idx) for idx in rows), key=lambda i: i.row())
    min_row = ordered[0].row()
    max_row = ordered[-1].row()
    parent_count = model.rowCount(parent)

    target_parent = parent
    if up:
        if min_row > 0:
            target_row = min_row - 1
        else:
            parent_row0 = _row0(model, parent)
            if not parent_row0.isValid() or _is_root_index(model, parent_row0):
                return False
            target_parent = parent_row0.parent()
            target_row = parent_row0.row()
    else:
        if max_row < parent_count - 1:
            # pre-pop index (+2) for a one-row downward move of a selected block
            target_row = max_row + 2
        else:
            parent_row0 = _row0(model, parent)
            if not parent_row0.isValid() or _is_root_index(model, parent_row0):
                return False
            target_parent = parent_row0.parent()
            target_row = parent_row0.row() + 1

    return tab.push_move_rows(ordered, target_parent, target_row, label="move up" if up else "move down")


def _multi_parent_common_grandparent_move(tab, model, rows: list, *, up: bool) -> bool:
    parent_rows = [_row0(model, idx.parent()) for idx in rows]
    if any(not p.isValid() or _is_root_index(model, p) for p in parent_rows):
        return False

    grandparent_paths = {_index_path(p.parent()) for p in parent_rows}
    if len(grandparent_paths) != 1:
        return False

    for idx in rows:
        parent = idx.parent()
        if up and idx.row() != 0:
            return False
        if not up and idx.row() != model.rowCount(parent) - 1:
            return False

    unique_parents = sorted({_index_path(p): p for p in parent_rows}.values(), key=_index_path)
    target_parent = unique_parents[0].parent()
    if up:
        target_row = min(p.row() for p in unique_parents)
    else:
        target_row = max(p.row() for p in unique_parents) + 1

    ordered = sorted((_row0(model, idx) for idx in rows), key=_index_path)
    return tab.push_move_rows(ordered, target_parent, target_row, label="move up" if up else "move down")


def _move_multi_parent_fallback(tab, model, rows: list, *, up: bool) -> bool:
    ordered = list(rows if up else reversed(rows))
    operations: list[tuple[tuple[int, ...], int, int]] = []

    for idx in ordered:
        parent = idx.parent()
        source_row = idx.row()
        if up:
            if source_row <= 0:
                continue
            target_row = source_row - 1
        else:
            if source_row >= model.rowCount(parent) - 1:
                continue
            target_row = source_row + 2
        operations.append((_index_path(parent), source_row, target_row))

    if not operations:
        return False

    moved = 0
    # Track final positions (parent_path → dest_row) so we can re-select after.
    final_positions: list[tuple[tuple[int, ...], int]] = []

    tab.undo_stack.beginMacro("move up" if up else "move down")
    try:
        for parent_path, source_row, target_row in operations:
            parent = tab._index_from_path(parent_path)
            source_idx = model.index(source_row, 0, parent)
            if not source_idx.isValid():
                continue
            if tab.push_move_rows([source_idx], parent, target_row, label="move up" if up else "move down"):
                # For a same-parent move, pre-pop target_row adjusts:
                # up: source > target so no adjustment → lands at target_row (= source_row - 1)
                # down: source < target so adjustment subtracts 1 → lands at target_row - 1 (= source_row + 1)
                dest = target_row if up else target_row - 1
                final_positions.append((parent_path, dest))
                moved += 1
    finally:
        tab.undo_stack.endMacro()

    if 0 < moved < len(rows):
        _status_partial_move(tab)

    # Restore the full multi-selection for all moved rows.
    if final_positions:
        sm = tab.view.selectionModel()
        selection = QItemSelection()
        first_view_idx = None
        for parent_path, row in final_positions:
            src_idx = model.index(row, 0, tab._index_from_path(parent_path))
            view_idx = tab._source_to_view(src_idx)
            if view_idx.isValid():
                selection.select(view_idx, view_idx)
                if first_view_idx is None:
                    first_view_idx = view_idx
        sm.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        if first_view_idx is not None:
            sm.setCurrentIndex(first_view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)

    return moved > 0


def _move_selection_with_tab(tree_view: QTreeView, *, up: bool) -> bool:
    model, rows = _ordered_non_root_rows(tree_view)
    if model is None or not rows:
        return False

    tab = _tab_of(tree_view)
    if tab is None:
        return False

    if not selection_spans_multiple_parents(rows):
        return _move_same_parent(tab, model, rows, up=up)

    if _multi_parent_common_grandparent_move(tab, model, rows, up=up):
        return True
    return _move_multi_parent_fallback(tab, model, rows, up=up)


def move_selection_up(tree_view: QTreeView) -> bool:
    tab = _tab_of(tree_view)
    if tab is not None:
        return _move_selection_with_tab(tree_view, up=True)

    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if not current.isValid():
        return False

    return action_move_up(tree_view, current, model)


def move_selection_down(tree_view: QTreeView) -> bool:
    tab = _tab_of(tree_view)
    if tab is not None:
        return _move_selection_with_tab(tree_view, up=False)

    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if not current.isValid():
        return False

    return action_move_down(tree_view, current, model)


def sort_selection_keys(tree_view: QTreeView, recursive: bool = False) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if current.isValid():
        row0 = _row0(model, current)
    elif model.show_root:
        row0 = model.index(0, 0, QModelIndex())
    else:
        return False

    tab = _tab_of(tree_view)
    if tab is not None:
        return tab.push_sort_keys(row0, recursive=recursive)

    return action_sort_keys(current, model, recursive=recursive)


def expand_all(tree_view: QTreeView) -> bool:
    tree_view.expandAll()
    return True


def collapse_all(tree_view: QTreeView) -> bool:
    tree_view.collapseAll()
    return True
