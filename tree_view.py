from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtWidgets import QApplication, QMenu, QTreeView

from enums import JsonType
from jsontream import StreamingJSONEncoderWrapper
from model_actions import action_insert_child, action_insert_row
from mpq2py import mpq_json_default
from tree_model import JsonTreeModel

MIME_JSON_TREE = "application/x-json-tree"


def show_context_menu(tree_view: QTreeView, position: QPoint):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    model = tree_view.model()

    if isinstance(model, JsonTreeModel) and index.isValid():
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

    new_row = context_menu.addAction("Insert Row")
    new_row.triggered.connect(lambda: action_insert_row(index, model))

    new_child = context_menu.addAction("Insert Child")
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


def copy_selection(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    rows = sorted(_top_level_selected_rows(tree_view), key=_index_path)
    if not rows:
        return False

    items = [model.get_item(idx).to_json() for idx in rows]
    payload: Any = items[0] if len(items) == 1 else items

    text = json.dumps(payload, default=mpq_json_default, indent=2)
    metadata = json.dumps({"items": items}, default=mpq_json_default)

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


def _clipboard_items() -> list[Any] | None:
    md = QApplication.clipboard().mimeData()
    if md is None:
        return None

    if md.hasFormat(MIME_JSON_TREE):
        try:
            raw = bytes(md.data(MIME_JSON_TREE)).decode("utf-8")
            parsed = json.loads(raw)
            items = parsed.get("items") if isinstance(parsed, dict) else None
            if isinstance(items, list):
                return items
        except Exception:
            pass

    text = md.text().strip()
    if not text:
        return None

    try:
        return [json.loads(text)]
    except Exception:
        return None


def paste_from_clipboard(tree_view: QTreeView) -> bool:
    model = tree_view.model()
    if not isinstance(model, JsonTreeModel):
        return False

    values = _clipboard_items()
    if not values:
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

    inserted = 0
    for value in values:
        row = insert_pos + inserted
        if not model.insertRow(row, parent_index):
            break
        value_index = model.index(row, 2, parent_index)
        if model.setData(value_index, value, Qt.ItemDataRole.EditRole):
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
