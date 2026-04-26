from __future__ import annotations

import json
from typing import Any

import simplejson
from PySide6.QtCore import QMimeData, QModelIndex, QPoint, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QApplication, QMenu, QTreeView

from enums import JsonType
from jsontream import StreamingJSONEncoderWrapper
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
from mpq2py import mpq_json_default
from tree_model import JsonTreeModel

MIME_JSON_TREE = "application/x-json-tree"


def _resolve_model(tree_view: QTreeView) -> tuple[JsonTreeModel | None, QSortFilterProxyModel | None]:
    model = tree_view.model()
    if isinstance(model, JsonTreeModel):
        return model, None
    if isinstance(model, QSortFilterProxyModel) and isinstance(model.sourceModel(), JsonTreeModel):
        return model.sourceModel(), model
    return None, None


def _to_source_index(index: QModelIndex) -> QModelIndex:
    model = index.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.mapToSource(index)
    return index


def _to_view_index(tree_view: QTreeView, index: QModelIndex) -> QModelIndex:
    _source_model, proxy = _resolve_model(tree_view)
    if proxy is None:
        return index
    return proxy.mapFromSource(index)


def show_context_menu(tree_view: QTreeView, position: QPoint):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    source_model, _proxy = _resolve_model(tree_view)
    if index.isValid():
        tree_view.setCurrentIndex(index)

    can_insert_child = False
    can_sort_keys = False
    can_move_up = False
    can_move_down = False
    if source_model is not None and index.isValid():
        source_index = _to_source_index(index)
        row0 = source_model.index(source_index.row(), 0, source_index.parent())
        item = source_model.get_item(row0)
        can_insert_child = item.json_type in (JsonType.OBJECT, JsonType.ARRAY)
        can_sort_keys = item.json_type is JsonType.OBJECT
        can_move_up = row0.row() > 0
        can_move_down = row0.row() < source_model.rowCount(row0.parent()) - 1

        data = tree_view.model().data(index, Qt.ItemDataRole.DisplayRole)
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
    before_action.triggered.connect(lambda: insert_sibling_before(tree_view))

    after_action = context_menu.addAction("Insert Sibling After")
    after_action.triggered.connect(lambda: insert_sibling_after(tree_view))

    new_child = context_menu.addAction("Insert Child")
    new_child.setEnabled(can_insert_child)
    new_child.triggered.connect(lambda: insert_child_current(tree_view))

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
    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None:
        return []

    selection = tree_view.selectionModel()
    if selection is None:
        return []

    rows = selection.selectedRows(0)
    if rows:
        return [_to_source_index(idx) for idx in rows]

    current = selection.currentIndex()
    if not current.isValid():
        return []
    source_current = _to_source_index(current)
    return [source_model.index(source_current.row(), 0, source_current.parent())]


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
    model, _proxy = _resolve_model(tree_view)
    if model is None:
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


def _commit_on_tab(tree_view: QTreeView, text: str, mutator) -> bool:
    tab = tree_view.parent()
    if tab is not None and hasattr(tab, "commit_mutation"):
        return bool(tab.commit_mutation(text, mutator))
    return bool(mutator())


def _tab_of(tree_view: QTreeView):
    """Return the parent ``JsonTab`` if it exposes the typed-command API."""
    parent = tree_view.parent()
    if parent is not None and hasattr(parent, "push_insert_rows"):
        return parent
    return None


def _row0(model: JsonTreeModel, index: QModelIndex) -> QModelIndex:
    if not index.isValid():
        return QModelIndex()
    return model.index(index.row(), 0, index.parent())


def _is_root_index(model: JsonTreeModel, index: QModelIndex) -> bool:
    return bool(index.isValid() and model.get_item(index) is model.root_item)


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

    # Fallback: direct (non-undo) removal, deepest/last-row first.
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
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    entries = _clipboard_entries()
    if not entries:
        return False
    entries_list = entries

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
        for offset, entry in enumerate(entries_list):
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

    # Fallback: direct (non-undo) paste path.
    inserted = 0
    for entry in entries_list:
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


def to_json(item):
    encoder = StreamingJSONEncoderWrapper(separators=(",", ":"), indent=2)
    source = item.to_json() if hasattr(item, "to_json") else item
    return "".join(encoder.iterencode(source))


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
        inserts: list[dict[str, Any]] = []
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
        # ``_InsertRowsCmd`` redoes inserts in the recorded order. Inserts at
        # higher rows happen first; lower-row inserts that come later are
        # unaffected by them. Undo runs in reverse order.
        return tab.push_insert_rows(inserts, label="duplicate", target_qname=first_source_qname)

    # Fallback: non-undo duplicate.
    changed = False
    for idx in ordered:
        changed = action_duplicate(tree_view, idx, model) or changed
    return changed


def move_selection_up(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if not current.isValid():
        return False

    row0 = _row0(model, current)
    if _is_root_index(model, row0):
        return False
    if row0.row() <= 0:
        return False

    tab = _tab_of(tree_view)
    if tab is not None:
        return tab.push_move_row(row0.parent(), row0.row(), row0.row() - 1, label="move up")

    return action_move_up(tree_view, current, model)


def move_selection_down(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    current = _to_source_index(tree_view.currentIndex())
    if not current.isValid():
        return False

    row0 = _row0(model, current)
    if _is_root_index(model, row0):
        return False
    parent = row0.parent()
    if row0.row() >= model.rowCount(parent) - 1:
        return False

    tab = _tab_of(tree_view)
    if tab is not None:
        return tab.push_move_row(parent, row0.row(), row0.row() + 1, label="move down")

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
