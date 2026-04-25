from __future__ import annotations

import json
from typing import Any

import simplejson
from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtWidgets import QApplication, QMenu, QTreeView

from enums import JsonType
from jsontream import StreamingJSONEncoderWrapper
from model_actions import (
    action_duplicate,
    action_insert_child,
    action_insert_row_after,
    action_insert_row_before,
    action_sort_keys,
)
from mpq2py import mpq_json_default
from tree_model import JsonTreeModel

MIME_JSON_TREE = "application/x-json-tree"


def show_context_menu(tree_view: QTreeView, position: QPoint):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    model = tree_view.model()

    can_insert_child = False
    can_sort_keys = False
    can_move_up = False
    can_move_down = False
    if isinstance(model, JsonTreeModel) and index.isValid():
        row0 = index.siblingAtColumn(0)
        item = model.get_item(row0)
        can_insert_child = item.json_type in (JsonType.OBJECT, JsonType.ARRAY)
        can_sort_keys = item.json_type is JsonType.OBJECT
        can_move_up = row0.row() > 0
        can_move_down = row0.row() < model.rowCount(row0.parent()) - 1

        data = model.data(index, Qt.ItemDataRole.DisplayRole)
        item_menu = context_menu.addMenu(str(data) if data is not None else "Item")

        copy_action = item_menu.addAction("Copy")
        copy_action.triggered.connect(lambda: copy_selection(tree_view))

        cut_action = item_menu.addAction("Cut")
        cut_action.triggered.connect(lambda: cut_selection(tree_view))

        paste_action = item_menu.addAction("Paste")
        paste_action.triggered.connect(lambda: paste_from_clipboard(tree_view))

        delete_action = item_menu.addAction("Delete")
        delete_action.triggered.connect(lambda: delete_selection(tree_view))

        duplicate_action = item_menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: duplicate_selection(tree_view))

        move_up_action = item_menu.addAction("Move Up")
        move_up_action.setEnabled(can_move_up)
        move_up_action.triggered.connect(lambda: move_selection_up(tree_view))

        move_down_action = item_menu.addAction("Move Down")
        move_down_action.setEnabled(can_move_down)
        move_down_action.triggered.connect(lambda: move_selection_down(tree_view))

        sort_action = item_menu.addAction("Sort Keys")
        sort_action.setEnabled(can_sort_keys)
        sort_action.triggered.connect(lambda: sort_selection_keys(tree_view, recursive=False))

        sort_recursive_action = item_menu.addAction("Sort Keys (Recursive)")
        sort_recursive_action.setEnabled(can_sort_keys)
        sort_recursive_action.triggered.connect(lambda: sort_selection_keys(tree_view, recursive=True))

    before_action = context_menu.addAction("Insert Sibling Before")
    before_action.triggered.connect(lambda: action_insert_row_before(index, model))

    after_action = context_menu.addAction("Insert Sibling After")
    after_action.triggered.connect(lambda: action_insert_row_after(index, model))

    new_child = context_menu.addAction("Insert Child")
    new_child.setEnabled(can_insert_child)
    new_child.triggered.connect(lambda: action_insert_child(tree_view, index, model))

    context_menu.exec(tree_view.mapToGlobal(position))


def _index_path(index) -> tuple[int, ...]:
    path: list[int] = []
    cursor = index
    while cursor.isValid():
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


def _is_ancestor(ancestor, index) -> bool:
    parent = index.parent()
    while parent.isValid():
        if parent == ancestor:
            return True
        parent = parent.parent()
    return False


def _selected_rows(tree_view: QTreeView) -> list:
    selection = tree_view.selectionModel()
    if selection is None:
        return []

    rows = selection.selectedRows(0)
    if rows:
        return rows

    current = selection.currentIndex()
    return [current.siblingAtColumn(0)] if current.isValid() else []


def _top_level_selected_rows(tree_view: QTreeView) -> list:
    rows = [idx for idx in _selected_rows(tree_view) if idx.isValid()]
    return [idx for idx in rows if not any(_is_ancestor(other, idx) for other in rows if other != idx)]


def _build_copy_entries(model: JsonTreeModel, rows) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx in rows:
        item = model.get_item(idx)
        entries.append(
            {
                "name": item.name if isinstance(item.name, str) else None,
                "value": item.to_json(),
            }
        )
    return entries


def _entries_text_payload(model: JsonTreeModel, rows, entries: list[dict[str, Any]]) -> Any:
    if not entries:
        return None

    first_parent = rows[0].parent()
    same_parent = all(idx.parent() == first_parent for idx in rows)
    all_named = all(isinstance(entry.get("name"), str) and entry["name"] for entry in entries)

    if same_parent and all_named:
        parent_item = model.get_item(first_parent)
        if parent_item.json_type is JsonType.OBJECT:
            names = [entry["name"] for entry in entries]
            if len(set(names)) == len(names):
                return {entry["name"]: entry["value"] for entry in entries}

    if len(entries) == 1:
        return entries[0]["value"]
    return [entry["value"] for entry in entries]


def copy_selection(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    rows = sorted(_top_level_selected_rows(tree_view), key=_index_path)
    if not rows:
        return False

    entries = _build_copy_entries(model, rows)
    text_payload = _entries_text_payload(model, rows, entries)

    text = simplejson.dumps(text_payload, default=mpq_json_default, indent=2)
    metadata = simplejson.dumps({"entries": entries}, default=mpq_json_default)

    mime = QMimeData()
    mime.setData(MIME_JSON_TREE, metadata.encode("utf-8"))
    mime.setText(text)
    QApplication.clipboard().setMimeData(mime)
    return True


def delete_selection(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    rows = _top_level_selected_rows(tree_view)
    if not rows:
        return False

    # Delete deepest/surviving rows first so row offsets stay valid.
    rows = sorted(rows, key=lambda idx: (_index_path(idx.parent()), idx.row()), reverse=True)

    changed = False
    for idx in rows:
        changed = model.removeRow(idx.row(), idx.parent()) or changed
    return changed


def cut_selection(tree_view: QTreeView) -> bool:
    if not copy_selection(tree_view):
        return False
    return delete_selection(tree_view)


def _clipboard_entries() -> list[dict[str, Any]] | None:
    md = QApplication.clipboard().mimeData()
    if md is None:
        return None

    if md.hasFormat(MIME_JSON_TREE):
        try:
            raw = md.data(MIME_JSON_TREE).data().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                entries = parsed.get("entries")
                if isinstance(entries, list):
                    normalized: list[dict[str, Any]] = []
                    for entry in entries:
                        if not isinstance(entry, dict) or "value" not in entry:
                            continue
                        name = entry.get("name")
                        normalized.append({"name": name if isinstance(name, str) else None, "value": entry["value"]})
                    if normalized:
                        return normalized

                # Backward compatibility with old clipboard payload format.
                items = parsed.get("items")
                if isinstance(items, list):
                    return [{"name": None, "value": value} for value in items]
        except Exception:
            pass

    text = md.text().strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    if isinstance(parsed, dict):
        return [{"name": str(name), "value": value} for name, value in parsed.items()]
    if isinstance(parsed, list):
        return [{"name": None, "value": value} for value in parsed]
    return [{"name": None, "value": parsed}]


def paste_from_clipboard(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    entries = _clipboard_entries()
    if not entries:
        return False

    current = tree_view.currentIndex()
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

    tree_view.setCurrentIndex(model.index(insert_pos, 0, parent_index))
    return True


def to_json(item):
    encoder = StreamingJSONEncoderWrapper(separators=(",", ":"), indent=2)
    source = item.to_json() if hasattr(item, "to_json") else item
    return "".join(encoder.iterencode(source))


def duplicate_selection(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    rows = _top_level_selected_rows(tree_view)
    if not rows:
        return False

    changed = False
    for idx in sorted(rows, key=_index_path, reverse=True):
        changed = action_duplicate(tree_view, idx, model) or changed
    return changed


def move_selection_up(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    current = tree_view.currentIndex()
    if not current.isValid():
        return False

    from model_actions import action_move_up

    return action_move_up(tree_view, current, model)


def move_selection_down(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    current = tree_view.currentIndex()
    if not current.isValid():
        return False

    from model_actions import action_move_down

    return action_move_down(tree_view, current, model)


def sort_selection_keys(tree_view: QTreeView, recursive: bool = False) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    current = tree_view.currentIndex()
    if not current.isValid():
        return False

    return action_sort_keys(current, model, recursive=recursive)
