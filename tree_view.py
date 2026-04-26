from __future__ import annotations

from typing import Any

import simplejson
from PySide6.QtCore import QModelIndex, QPoint, Qt
from PySide6.QtWidgets import QMenu, QTreeView

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
from tree_actions.clipboard import MIME_JSON_TREE, copy_selection
from tree_actions.paste import paste_from_clipboard
from tree_actions.selection import (
    _index_path,
    _is_ancestor,
    _is_root_index,
    _resolve_model,
    _row0,
    _selected_rows,
    _to_source_index,
    _to_view_index,
    _top_level_selected_rows,
)
from tree_model import JsonTreeModel


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

    context_menu.addSeparator()

    expand_all_action = context_menu.addAction("Expand All")
    expand_all_action.triggered.connect(lambda: expand_all(tree_view))

    collapse_all_action = context_menu.addAction("Collapse All")
    collapse_all_action.triggered.connect(lambda: collapse_all(tree_view))

    context_menu.exec(tree_view.mapToGlobal(position))


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


def expand_all(tree_view: QTreeView) -> bool:
    tree_view.expandAll()
    return True


def collapse_all(tree_view: QTreeView) -> bool:
    tree_view.collapseAll()
    return True
