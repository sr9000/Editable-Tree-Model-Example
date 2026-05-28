"""Typed undo-command push helpers for :class:`documents.tab.JsonTab`.

These were originally methods on ``JsonTab`` itself.  Extracting them here keeps
``JsonTab`` lean while preserving the existing ``tab.push_*`` call sites used by
the test suite — those become one-line forwarders.

Module-level functions take the owning ``JsonTab`` as their first argument and
reach back through it for tree-model / view / undo-stack access.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex

from documents.tab_number_types import would_drop_fraction_on_type_change
from tree.types import JsonType
from undo.commands import (
    _ChangeTypeCmd,
    _EditValueCmd,
    _InsertRowsCmd,
    _MoveRowsCmd,
    _RemoveRowsCmd,
    _RenameCmd,
    _SortKeysCmd,
    _SwitchFieldCaseCmd,
)

if TYPE_CHECKING:
    from documents.tab import JsonTab
    from tree_actions.anchors import MoveAnchor


def make_label(text: str, target_qname: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    return f"[{timestamp}] {text} @ {target_qname}"


def push_move_row(
    tab: JsonTab,
    parent_index: QModelIndex,
    src: int,
    dst: int,
    *,
    label: str = "move row",
) -> bool:
    if tab.data_store.is_read_only:
        return False
    if src == dst:
        return False
    parent_item = tab.data_store.model.get_item(parent_index)
    n = parent_item.child_count()
    if not (0 <= src < n and 0 <= dst < n):
        return False
    source_idx = tab.data_store.model.index(src, 0, parent_index)
    # push_move_rows uses pre-pop target_row; dst is post-pop.
    # Forward move (src < dst): removing src shifts later rows down by 1,
    # so pre-pop target = dst + 1 to land at the same final position.
    # Backward move (src > dst): no shift needed, pre-pop target = dst.
    pre_pop_target = dst + 1 if src < dst else dst
    return push_move_rows(tab, [source_idx], parent_index, pre_pop_target, label=label)


def push_move_rows_anchor(
    tab: JsonTab,
    sources: list,
    anchor: MoveAnchor,
    *,
    label: str = "move rows",
) -> bool:
    """Move *sources* to the gap described by ``anchor`` as a single undo command.

    Returns ``False`` when:
    - *sources* is empty,
    - any source would become an ancestor of ``anchor.parent_path``
      (cycle guard), or
    - the move is a no-op (block already lands at the anchor).
    """
    from tree_actions.anchors import anchor_is_cycle, anchor_is_no_op, resolve_anchor_insert_row

    if tab.data_store.is_read_only:
        return False
    if not sources:
        return False

    model = tab.data_store.model
    # Snapshot every source's (parent_path, row) BEFORE any mutation.
    source_paths: list[tuple[tuple, int]] = []
    source_names: list[Any] = []
    for idx in sources:
        row0 = model.index(idx.row(), 0, idx.parent())
        source_paths.append((tab._index_path(row0.parent()), row0.row()))
        source_names.append(model.get_item(row0).name)

    # Cycle guard.
    if anchor_is_cycle(anchor, source_paths):
        tab.show_status("Cannot move a parent into its own descendant", 3000)
        return False

    # No-op guard (path-only). For at_end, resolve to a concrete row first
    # and compare against the would-be insert position.
    if anchor_is_no_op(anchor, source_paths):
        return False
    if anchor.is_at_end:
        resolve_anchor_insert_row(model, tab, anchor, source_paths)
        same_parent_sources = sorted(r for p, r in source_paths if p == anchor.parent_path)
        if same_parent_sources:
            parent_index = tab._index_from_path(anchor.parent_path)
            parent_count = model.rowCount(parent_index)
            last_src = same_parent_sources[-1]
            is_contiguous = all(b - a == 1 for a, b in zip(same_parent_sources, same_parent_sources[1:]))
            # If the block is contiguous and already sits as the suffix, at_end is a no-op.
            if is_contiguous and last_src == parent_count - 1 and len(same_parent_sources) == len(source_paths):
                return False

    # Build the command.
    move_view_state = tab._capture_move_view_state(sources)
    target_qname = tab._qualified_name(model.index(sources[0].row(), 0, sources[0].parent()))
    cmd = _MoveRowsCmd(tab, make_label(label, target_qname), source_paths, source_names, anchor)
    tab.data_store.undo_stack.push(cmd)
    tab.data_store._move_view_state_by_cmd_id[id(cmd)] = move_view_state
    # Expose placed paths for action-layer post-hooks (esp. macros).
    tab.data_store._last_move_placed = cmd.placed_paths
    tab._apply_move_view_state(cmd, undo=False)
    return True


def push_move_rows(
    tab: JsonTab,
    sources: list,
    target_parent: QModelIndex,
    target_row: int,
    *,
    label: str = "move rows",
) -> bool:
    """Legacy pre-Step-9 API. Translates ``(target_parent, target_row)``
    (pre-pop convention) into a ``MoveAnchor`` and delegates."""
    from tree_actions.anchors import pre_pop_target_row_to_anchor

    if tab.data_store.is_read_only:
        return False
    if not sources:
        return False
    anchor = pre_pop_target_row_to_anchor(tab, target_parent, target_row)
    return push_move_rows_anchor(tab, sources, anchor, label=label)


def push_rename(tab: JsonTab, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool:
    if tab.data_store.is_read_only:
        return False
    if not name_index.isValid() or name_index.column() != 0:
        return False
    item = tab.data_store.model.get_item(name_index)
    if not isinstance(new_name, str):
        return False
    candidate = new_name.strip()
    if not candidate or candidate == item.name:
        return False
    if item.parent_item is None or item.parent_item.json_type is JsonType.ARRAY:
        return False
    if item.parent_item.json_type is JsonType.OBJECT:
        siblings = {c.name for c in item.parent_item.child_items if c is not item and isinstance(c.name, str)}
        if candidate in siblings:
            return False
    target_qname = tab._qualified_name(name_index)
    cmd = _RenameCmd(tab, make_label(label, target_qname), tab._index_path(name_index), item.name, candidate)
    tab.data_store.undo_stack.push(cmd)
    return True


def push_edit_value(tab: JsonTab, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
    if tab.data_store.is_read_only:
        return False
    if not value_index.isValid() or value_index.column() != 2:
        return False
    name_idx = tab.data_store.model.index(value_index.row(), 0, value_index.parent())
    item = tab.data_store.model.get_item(name_idx)
    old_subtree = item.to_json()
    # Honour explicit_type strict coercion when the type was pinned.
    if item.explicit_type and item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
        ok, coerced = item._coerce_value_for_type(item.json_type, new_value, strict=True)
        if not ok:
            return False
        applied = coerced
    else:
        applied = new_value
    # No-op detection on the affected subtree (subset comparison).
    if old_subtree == applied and isinstance(applied, type(old_subtree)):
        return False
    target_qname = tab._qualified_name(name_idx)
    cmd = _EditValueCmd(tab, make_label(label, target_qname), tab._index_path(name_idx), old_subtree, applied)
    tab.data_store.undo_stack.push(cmd)
    return True


def push_change_type(tab: JsonTab, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
    if tab.data_store.is_read_only:
        return False
    if not type_index.isValid() or type_index.column() != 1:
        return False
    try:
        target_type = new_type if isinstance(new_type, JsonType) else JsonType(str(new_type))
    except ValueError:
        return False
    name_idx = tab.data_store.model.index(type_index.row(), 0, type_index.parent())
    item = tab.data_store.model.get_item(name_idx)
    if item.json_type is target_type:
        return False
    warn_fraction_loss = would_drop_fraction_on_type_change(item, target_type)
    old_subtree = item.to_json()
    old_explicit = item.explicit_type
    old_type = item.json_type
    target_qname = tab._qualified_name(name_idx)
    cmd = _ChangeTypeCmd(
        tab,
        make_label(label, target_qname),
        tab._index_path(name_idx),
        old_subtree,
        old_explicit,
        old_type,
        target_type,
    )
    tab.data_store.undo_stack.push(cmd)
    if warn_fraction_loss:
        tab.show_status("Fractional part discarded during float-to-integer conversion", 3000)
    return True


def push_insert_rows(
    tab: JsonTab,
    inserts: list,
    *,
    label: str = "insert",
    target_qname: str | None = None,
) -> bool:
    """``inserts`` is a list of ``{parent_path, row, value, name}``."""
    if tab.data_store.is_read_only:
        return False
    if not inserts:
        return False
    qname = (
        target_qname
        if target_qname is not None
        else tab._qualified_name(tab._index_from_path(inserts[0]["parent_path"]))
    )
    cmd = _InsertRowsCmd(tab, make_label(label, qname), inserts)
    tab.data_store.undo_stack.push(cmd)
    return True


def push_remove_rows(tab: JsonTab, indexes: list, *, label: str = "delete") -> bool:
    if tab.data_store.is_read_only:
        return False
    if not indexes:
        return False
    ordered = sorted(indexes, key=lambda i: (tab._index_path(i.parent()), i.row()), reverse=True)
    removals = []
    for idx in ordered:
        row0 = tab.data_store.model.index(idx.row(), 0, idx.parent())
        item = tab.data_store.model.get_item(row0)
        removals.append(
            {
                "parent_path": tab._index_path(idx.parent()),
                "row": idx.row(),
                "name": item.name,
                "value": item.to_json(),
            }
        )
    target_qname = tab._qualified_name(ordered[0])
    cmd = _RemoveRowsCmd(tab, make_label(label, target_qname), removals)
    tab.data_store.undo_stack.push(cmd)
    return True


def push_sort_keys(tab: JsonTab, index: QModelIndex, *, recursive: bool = False, label: str | None = None) -> bool:
    if tab.data_store.is_read_only:
        return False
    if not index.isValid():
        return False
    item = tab.data_store.model.get_item(index)
    if item.json_type is not JsonType.OBJECT:
        return False
    old_subtree = item.to_json()
    if not recursive and list(old_subtree.keys()) == sorted(old_subtree.keys()):
        return False
    target_qname = tab._qualified_name(index)
    text = label if label is not None else ("sort keys recursive" if recursive else "sort keys")
    cmd = _SortKeysCmd(tab, make_label(text, target_qname), tab._index_path(index), old_subtree, recursive)
    tab.data_store.undo_stack.push(cmd)
    return True


def push_switch_field_case(
    tab: JsonTab,
    renames: list[dict[str, Any]],
    *,
    label: str = "switch field case",
    target_qname: str | None = None,
) -> bool:
    if tab.data_store.is_read_only:
        return False
    if not renames:
        return False

    normalized: list[dict[str, Any]] = []
    by_parent: dict[tuple[int, ...], dict[int, str]] = {}

    for rec in renames:
        path = tuple(rec.get("path", ()))
        old_name = rec.get("old_name")
        new_name = rec.get("new_name")
        if not path or not isinstance(old_name, str) or not isinstance(new_name, str):
            continue
        if old_name == new_name:
            continue
        idx = tab._index_from_path(path)
        if not idx.isValid():
            continue
        item = tab.data_store.model.get_item(idx)
        if item.name != old_name:
            continue
        parent = item.parent_item
        if parent is None or parent.json_type is not JsonType.OBJECT:
            continue
        normalized.append({"path": path, "old_name": old_name, "new_name": new_name})
        by_parent.setdefault(path[:-1], {})[path[-1]] = new_name

    if not normalized:
        return False

    # Preflight: reject operations that would create duplicate sibling names.
    for parent_path, updates in by_parent.items():
        parent_index = tab._index_from_path(parent_path)
        parent_item = tab.data_store.model.get_item(parent_index)
        final_names: list[str] = []
        for row, child in enumerate(parent_item.child_items):
            if not isinstance(child.name, str):
                continue
            final_names.append(updates.get(row, child.name))
        if len(set(final_names)) != len(final_names):
            return False

    first_index = tab._index_from_path(normalized[0]["path"])
    qname = target_qname if target_qname is not None else tab._qualified_name(first_index)
    cmd = _SwitchFieldCaseCmd(tab, make_label(label, qname), normalized)
    tab.data_store.undo_stack.push(cmd)
    return True
