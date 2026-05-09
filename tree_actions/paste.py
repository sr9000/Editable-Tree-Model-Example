from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from tree.types import JsonType
from tree_actions.clipboard import _clipboard_entries
from tree_actions.selection import _resolve_model, _row0, _to_source_index, _to_view_index


def _tab_of(tree_view: QTreeView):
    parent = tree_view.parent()
    if parent is not None and hasattr(parent, "push_insert_rows"):
        return parent
    return None


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


def _paste_entries_at(tree_view: QTreeView, parent_index: QModelIndex, insert_pos: int, *, label: str) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    entries = _clipboard_entries()
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
                    "parent_path": tab._index_path(parent_index),
                    "row": insert_pos + offset,
                    "value": entry["value"],
                    "name": name,
                }
            )
        ok = tab.push_insert_rows(inserts, label=label)
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
        return tab.push_edit_value(value_index, new_value, label="paste replace")

    return bool(model.setData(value_index, new_value, Qt.ItemDataRole.EditRole))
