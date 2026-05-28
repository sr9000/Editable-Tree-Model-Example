from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from tree.types import JsonType
from tree_actions._tab_lookup import find_owning_tab
from tree_actions.clipboard import _clipboard_entries
from tree_actions.selection import (
    _index_path,
    _resolve_model,
    _row0,
    _selected_rows,
    _to_source_index,
    _to_view_index,
    selected_source_rows,
    top_level_source_rows,
)


def _tab_of(tree_view: QTreeView):
    return find_owning_tab(tree_view)


def has_clipboard_entries() -> bool:
    """Return True if the clipboard currently contains paste-able tree entries."""
    return bool(_clipboard_entries())


def _resolve_paste_target(model, current: QModelIndex, mode: str):
    """Return (parent_index, insert_pos) for the requested placement mode, or
    ``None`` if the placement is not valid for the current selection.

    mode:
      - "auto":   container current → child append; primitive → sibling after; invalid → root append
      - "before": before current sibling
      - "after":  after current sibling
      - "child":  append as last child (current must be a container)
    """
    if mode == "auto":
        if current.isValid():
            row0 = current.siblingAtColumn(0)
            current_item = model.get_item(row0)
            if current_item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
                return row0, model.rowCount(row0)
            return row0.parent(), row0.row() + 1
        return QModelIndex(), model.rowCount(QModelIndex())

    if not current.isValid():
        # No selection: before/after/child all degrade to root append.
        return QModelIndex(), model.rowCount(QModelIndex())

    row0 = _row0(model, current)

    if mode == "child":
        item = model.get_item(row0)
        if item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
            return None
        return row0, model.rowCount(row0)

    if mode == "before":
        return row0.parent(), row0.row()
    if mode == "after":
        return row0.parent(), row0.row() + 1
    return None


def paste_entries_at(
    tree_view: QTreeView,
    parent_index: QModelIndex,
    insert_pos: int,
    entries: list[dict[str, Any]],
    *,
    label: str,
) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    if not entries:
        return False

    parent_item = model.get_item(parent_index)
    parent_is_object = parent_item.json_type is JsonType.OBJECT

    tab = _tab_of(tree_view)
    if tab is not None:
        used: set[str] = set()
        if parent_is_object:
            used = {c.name for c in parent_item.child_items if isinstance(c.name, str)}
        inserts: list[dict[str, Any]] = []
        for offset, entry in enumerate(entries):
            if parent_is_object:
                raw_name = entry.get("name")
                base = raw_name if isinstance(raw_name, str) and raw_name else "new_key"
                if base in used:
                    name = parent_item._unique_child_name(base, used_names=used - {base} | used)
                else:
                    name = base
                used.add(name)
            else:
                name = None
            inserts.append(
                {
                    "parent_path": tab.data_store.mutations.index_path(parent_index),
                    "row": insert_pos + offset,
                    "value": entry["value"],
                    "name": name,
                }
            )
        ok = tab.data_store.mutations.push_insert_rows(inserts, label=label)
        if ok and parent_index.isValid():
            tree_view.expand(_to_view_index(tree_view, parent_index))
        return ok

    inserted = 0
    for entry in entries:
        row = insert_pos + inserted
        if not model.insertRow(row, parent_index):
            break

        if parent_is_object and isinstance(entry.get("name"), str):
            name_index = model.index(row, 0, parent_index)
            model.setData(name_index, entry["name"], Qt.ItemDataRole.EditRole)

        value_index = model.index(row, 2, parent_index)
        if model.setData(value_index, entry["value"], Qt.ItemDataRole.EditRole):
            inserted += 1
            continue

        model.removeRow(row, parent_index)
        break

    if inserted <= 0:
        return False

    tree_view.setCurrentIndex(_to_view_index(tree_view, model.index(insert_pos, 0, parent_index)))
    return True


def _paste_entries_at(tree_view: QTreeView, parent_index: QModelIndex, insert_pos: int, *, label: str) -> bool:
    entries = _clipboard_entries()
    if not entries:
        return False
    return paste_entries_at(tree_view, parent_index, insert_pos, entries, label=label)


def paste_from_clipboard(tree_view: QTreeView) -> bool:
    """Smart paste: container current → child append, primitive → sibling after."""
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    current = _to_source_index(tree_view.currentIndex())
    target = _resolve_paste_target(model, current, "auto")
    if target is None:
        return False
    parent_index, insert_pos = target
    return _paste_entries_at(tree_view, parent_index, insert_pos, label="paste")


def paste_auto(tree_view: QTreeView) -> bool:
    """Default paste entrypoint used by shortcuts/menu.

    With multi-selection, clone all clipboard entries at every selected target.
    Otherwise keep the legacy single-target smart paste behavior.
    """
    rows = [idx for idx in selected_source_rows(tree_view) if idx.isValid()]
    if len(rows) > 1:
        return paste_clones_at_targets(tree_view)
    return paste_from_clipboard(tree_view)


def paste_before(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    current = _to_source_index(tree_view.currentIndex())
    target = _resolve_paste_target(model, current, "before")
    if target is None:
        return False
    parent_index, insert_pos = target
    return _paste_entries_at(tree_view, parent_index, insert_pos, label="paste before")


def paste_after(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    current = _to_source_index(tree_view.currentIndex())
    target = _resolve_paste_target(model, current, "after")
    if target is None:
        return False
    parent_index, insert_pos = target
    return _paste_entries_at(tree_view, parent_index, insert_pos, label="paste after")


def paste_as_child(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    current = _to_source_index(tree_view.currentIndex())
    target = _resolve_paste_target(model, current, "child")
    if target is None:
        return False
    parent_index, insert_pos = target
    return _paste_entries_at(tree_view, parent_index, insert_pos, label="paste as child")


def paste_replace_value(tree_view: QTreeView) -> bool:
    """Replace the value (entire subtree) of the current node with the
    clipboard value. Requires a single clipboard entry and a non-root
    selection."""
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    entries = _clipboard_entries()
    if not entries or len(entries) != 1:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if not current.isValid():
        return False

    row0 = _row0(model, current)
    item = model.get_item(row0)
    if item is model.root_item:
        return False

    new_value = entries[0]["value"]
    value_index = model.index(row0.row(), 2, row0.parent())

    tab = _tab_of(tree_view)
    if tab is not None:
        return tab.data_store.mutations.push_edit_value(value_index, new_value, label="paste replace")

    return bool(model.setData(value_index, new_value, Qt.ItemDataRole.EditRole))


# ---------------------------------------------------------------------------
# Step 9 — Multi-action paste helpers
# ---------------------------------------------------------------------------


def paste_clones_at_targets(tree_view: QTreeView) -> bool:
    """**Multi-paste.** Paste a clone of every clipboard entry at every
    currently-selected row.

    For container targets (OBJECT / ARRAY) the entries land as last
    children. For leaf targets the entries land as siblings immediately
    after the target. All inserts run inside a single ``QUndoStack``
    macro so undo restores the original tree in one step.

    Falls back to ``paste_from_clipboard`` when no row is selected.
    """
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    entries = _clipboard_entries()
    if not entries:
        return False

    selected = [_row0(model, idx) for idx in _selected_rows(tree_view) if idx.isValid()]
    if not selected:
        return paste_from_clipboard(tree_view)

    tab = _tab_of(tree_view)
    if tab is None:
        changed = False
        for target in selected:
            target_item = model.get_item(target)
            if target_item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
                parent_index = target
                insert_pos = model.rowCount(target)
            else:
                parent_index = target.parent()
                insert_pos = target.row() + 1
            changed = _paste_entries_at(tree_view, parent_index, insert_pos, label="paste") or changed
        return changed

    targets: list[tuple[tuple[int, ...], int]] = []
    for target in selected:
        target_item = model.get_item(target)
        if target_item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
            targets.append((tab.data_store.mutations.index_path(target), model.rowCount(target)))
        else:
            targets.append((tab.data_store.mutations.index_path(target.parent()), target.row() + 1))
    used_by_parent: dict[tuple[int, ...], set[str]] = {}
    inserts: list[dict[str, Any]] = []
    # Descending so earlier inserts in the same parent don't shift later positions.
    for parent_path, insert_pos in sorted(targets, key=lambda t: (t[0], t[1]), reverse=True):
        parent_index = tab.data_store.mutations.index_from_path(parent_path)
        parent_item = model.get_item(parent_index)
        parent_is_object = parent_item.json_type is JsonType.OBJECT
        if parent_is_object and parent_path not in used_by_parent:
            used_by_parent[parent_path] = {c.name for c in parent_item.child_items if isinstance(c.name, str)}
        used = used_by_parent.get(parent_path, set())
        for offset, entry in enumerate(entries):
            if parent_is_object:
                raw_name = entry.get("name")
                base = raw_name if isinstance(raw_name, str) and raw_name else "new_key"
                if base in used:
                    name = parent_item._unique_child_name(base, used_names=used)
                else:
                    name = base
                used.add(name)
            else:
                name = None
            inserts.append(
                {
                    "parent_path": parent_path,
                    "row": insert_pos + offset,
                    "value": entry["value"],
                    "name": name,
                }
            )

    if not inserts:
        return False
    return tab.data_store.mutations.push_insert_rows(inserts, label="paste at selection")


def paste_insert_after_zip(tree_view: QTreeView) -> bool:
    """**Multi-insert** (``Ctrl+Shift+V``).

    Zip-pair clipboard entries with top-level selected targets and insert each
    paired entry *after* its target row. Count mismatch policy is
    ``zip``-to-shortest. Uses :func:`top_level_source_rows` (no deep scan).
    """
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    entries = _clipboard_entries()
    if not entries:
        return False

    targets = sorted(
        [_row0(model, t) for t in top_level_source_rows(tree_view) if t.isValid()],
        key=_index_path,
    )
    if not targets:
        return False

    pairs = list(zip(targets, entries))
    if not pairs:
        return False

    tab = _tab_of(tree_view)
    if tab is None:
        changed = False
        for target, entry in sorted(pairs, key=lambda p: _index_path(p[0]), reverse=True):
            parent = target.parent()
            row = target.row() + 1
            if not model.insertRow(row, parent):
                continue
            if isinstance(entry.get("name"), str) and model.get_item(parent).json_type is JsonType.OBJECT:
                model.setData(model.index(row, 0, parent), entry["name"], Qt.ItemDataRole.EditRole)
            if model.setData(model.index(row, 2, parent), entry["value"], Qt.ItemDataRole.EditRole):
                changed = True
        return changed

    used_by_parent: dict[tuple[int, ...], set[str]] = {}
    inserts: list[dict[str, Any]] = []
    for target, entry in sorted(pairs, key=lambda p: _index_path(p[0]), reverse=True):
        parent = target.parent()
        parent_path = tab.data_store.mutations.index_path(parent)
        parent_item = model.get_item(parent)
        parent_is_object = parent_item.json_type is JsonType.OBJECT
        if parent_is_object and parent_path not in used_by_parent:
            used_by_parent[parent_path] = {c.name for c in parent_item.child_items if isinstance(c.name, str)}
        used = used_by_parent.get(parent_path, set())
        if parent_is_object:
            raw_name = entry.get("name")
            base = raw_name if isinstance(raw_name, str) and raw_name else "new_key"
            if base in used:
                name = parent_item._unique_child_name(base, used_names=used)
            else:
                name = base
            used.add(name)
        else:
            name = None
        inserts.append(
            {
                "parent_path": parent_path,
                "row": target.row() + 1,
                "value": entry["value"],
                "name": name,
            }
        )
    return tab.data_store.mutations.push_insert_rows(inserts, label="paste insert each")


def paste_replace_zip(tree_view: QTreeView) -> bool:
    """**Multi-replace**. Zip-pair clipboard top-level entries with top-level
    selected targets and replace each target's value with its paired entry.

    Policy on count mismatch: ``zip``-to-shortest. Uses
    :func:`top_level_source_rows` — no deep scan.
    """
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False
    entries = _clipboard_entries()
    if not entries:
        return False

    targets = sorted(
        [_row0(model, t) for t in top_level_source_rows(tree_view) if t.isValid()],
        key=_index_path,
    )
    if not targets:
        return False

    tab = _tab_of(tree_view)
    if tab is None:
        changed = False
        for target, entry in zip(targets, entries):
            value_index = model.index(target.row(), 2, target.parent())
            if model.setData(value_index, entry["value"], Qt.ItemDataRole.EditRole):
                changed = True
        return changed

    tab.data_store.mutations.begin_macro("paste replace each (zip)")
    moved = 0
    try:
        for target, entry in zip(targets, entries):
            value_index = model.index(target.row(), 2, target.parent())
            if tab.data_store.mutations.push_edit_value(value_index, entry["value"], label="paste replace each"):
                moved += 1
    finally:
        tab.data_store.mutations.end_macro()
    return moved > 0


def paste_insert_zip(tree_view: QTreeView) -> bool:
    """Backward-compatible alias for the renamed multi-replace action."""
    return paste_replace_zip(tree_view)
