from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMenu, QTreeView

from enums import JsonType
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_from_clipboard
from tree_actions.selection import _resolve_model, _to_source_index
from tree_actions.structure import (
    collapse_all,
    cut_selection,
    delete_selection,
    duplicate_selection,
    expand_all,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_up,
    sort_selection_keys,
)


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
