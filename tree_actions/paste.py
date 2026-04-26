from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeView

from enums import JsonType
from tree_actions.clipboard import _clipboard_entries
from tree_actions.selection import _resolve_model, _to_source_index, _to_view_index


def _tab_of(tree_view: QTreeView):
    parent = tree_view.parent()
    if parent is not None and hasattr(parent, "push_insert_rows"):
        return parent
    return None


def paste_from_clipboard(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    entries = _clipboard_entries()
    if not entries:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if current.isValid():
        current_row0 = current.siblingAtColumn(0)
        current_item = model.get_item(current_row0)

        if current_item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
            parent_index = current_row0
            insert_pos = model.rowCount(parent_index)
        else:
            parent_index = current_row0.parent()
            insert_pos = current_row0.row() + 1
    else:
        parent_index = current
        insert_pos = model.rowCount(parent_index)

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
        return tab.push_insert_rows(inserts, label="paste")

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
