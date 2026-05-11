from PySide6.QtCore import QModelIndex
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
from tree_actions.anchors import MoveAnchor, anchor_after_index, anchor_before_index
from tree_actions.clipboard import copy_selection
from tree_actions.selection import _index_path, _is_root_index, _resolve_model, _row0, _to_source_index, _to_view_index
from tree_actions.selection import top_level_source_rows as _top_level_selected_rows


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


# ---------------------------------------------------------------------------
# Step 9 — Anchor-based move (one algorithm, no per-shape branching)
# ---------------------------------------------------------------------------


def _group_rows_by_parent(model, rows: list) -> dict[tuple, list]:
    """Group source rows by their parent's source-model path."""
    groups: dict[tuple, list] = {}
    for idx in rows:
        row0 = _row0(model, idx)
        parent_path = _index_path(row0.parent())
        groups.setdefault(parent_path, []).append(row0)
    for plist in groups.values():
        plist.sort(key=lambda i: i.row())
    return groups


def _anchor_for_block(
    tab,
    model,
    parent_path: tuple,
    block_rows: list,
    *,
    up: bool,
) -> MoveAnchor | None:
    """Return the destination anchor for a same-parent contiguous *block*.

    If the block already touches the parent's boundary, bubble out to
    the grandparent. Returns ``None`` when the block is already at the
    top-level edge of the document (no place to bubble to).
    """
    parent_index = tab._index_from_path(parent_path)
    parent_count = model.rowCount(parent_index)
    first_row = block_rows[0].row()
    last_row = block_rows[-1].row()

    if up:
        if first_row > 0:
            # Land before the row currently sitting at first_row - 1.
            sibling_idx = model.index(first_row - 1, 0, parent_index)
            return anchor_before_index(sibling_idx, tab)
        # Boundary: bubble out to grandparent.
        parent_row0 = _row0(model, parent_index)
        if not parent_row0.isValid() or _is_root_index(model, parent_row0):
            return None
        return anchor_before_index(parent_row0, tab)

    # down
    if last_row < parent_count - 1:
        sibling_idx = model.index(last_row + 1, 0, parent_index)
        return anchor_after_index(sibling_idx, tab)
    parent_row0 = _row0(model, parent_index)
    if not parent_row0.isValid() or _is_root_index(model, parent_row0):
        return None
    return anchor_after_index(parent_row0, tab)


def _move_selection_with_tab(tree_view: QTreeView, *, up: bool) -> bool:
    """Single algorithm: group by parent → one anchor move per block.

    For each parent's contiguous group of selected siblings we compute
    *one* anchor and dispatch *one* ``push_move_rows_anchor`` call. All
    such calls in a multi-parent selection are wrapped in a single
    ``QUndoStack`` macro so undo restores the full selection in one step.
    """
    model, rows = _ordered_non_root_rows(tree_view)
    if model is None or not rows:
        return False

    tab = _tab_of(tree_view)
    if tab is None:
        return False

    groups = _group_rows_by_parent(model, rows)
    if not groups:
        return False

    # Per-group: capture (anchor, source_indexes). Re-resolution before each
    # push happens inside push_move_rows_anchor (paths are captured at push time).
    planned: list[tuple[tuple, MoveAnchor, list]] = []
    for parent_path, block_rows in groups.items():
        anchor = _anchor_for_block(tab, model, parent_path, block_rows, up=up)
        if anchor is None:
            continue
        planned.append((parent_path, anchor, list(block_rows)))

    if not planned:
        return False

    label = "move up" if up else "move down"

    # Single-block fast path — no macro overhead.
    if len(planned) == 1:
        _parent_path, anchor, block_rows = planned[0]
        return tab.push_move_rows_anchor(block_rows, anchor, label=label)

    # Multi-parent: macro of per-parent moves. Each child push captures source
    # paths AT push time, so earlier moves never leave later sources stale.
    placed_total: list[tuple[tuple, int]] = []
    moved = 0
    tab.undo_stack.beginMacro(label)
    try:
        for parent_path, anchor, block_rows in planned:
            # Re-resolve indexes from paths so any prior mutation is reflected.
            live_rows = [tab._index_from_path(parent_path + (idx.row(),)) for idx in block_rows]
            live_rows = [r for r in live_rows if r.isValid()]
            if not live_rows:
                continue
            if tab.push_move_rows_anchor(live_rows, anchor, label=label):
                placed_total.extend(getattr(tab, "_last_move_placed", []))
                moved += 1
    finally:
        tab.undo_stack.endMacro()

    if 0 < moved < len(planned):
        _status_partial_move(tab)

    if placed_total:
        tab._restore_selection_at_paths(placed_total)

    return moved > 0


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
