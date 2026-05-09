from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QComboBox, QMenu, QTreeView

from tree.types import JsonType
from tree_actions.clipboard import copy_selection, copy_selection_value_only, copy_selection_with_name
from tree_actions.paste import (
    has_clipboard_entries,
    paste_after,
    paste_as_child,
    paste_before,
    paste_from_clipboard,
    paste_replace_value,
)
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


def _add(menu: QMenu, text: str, slot, *, enabled: bool = True, shortcut: str | None = None):
    act = menu.addAction(text)
    if shortcut is not None:
        act.setShortcut(QKeySequence(shortcut))
    act.setEnabled(enabled)
    act.triggered.connect(slot)
    return act


def _find_enter_edit_target(host) -> object | None:
    cursor = host
    while cursor is not None:
        if hasattr(cursor, "edit_name_or_value_from_enter"):
            return cursor
        cursor = cursor.parent() if hasattr(cursor, "parent") else None
    return None


def _open_active_type_combo_popup(tree_view: QTreeView) -> bool:
    for combo in tree_view.findChildren(QComboBox):
        if combo.parent() is tree_view.viewport() and combo.isVisible():
            combo.showPopup()
            return True
    return False


def _trigger_type_combo_from_context_menu(tree_view: QTreeView, index) -> bool:
    if not index.isValid():
        return False
    type_index = index.siblingAtColumn(1)
    if not type_index.isValid():
        return False
    model = tree_view.model()
    if model is None:
        return False
    if not (model.flags(type_index) & Qt.ItemFlag.ItemIsEditable):
        return False

    tree_view.setCurrentIndex(type_index)

    tab = _find_enter_edit_target(tree_view)
    if tab is not None:
        trigger = getattr(tab, "edit_name_or_value_from_enter", None)
        if callable(trigger):
            trigger()
            return True

    tree_view.edit(type_index)
    QTimer.singleShot(0, lambda: _open_active_type_combo_popup(tree_view))
    return True


def show_context_menu(tree_view: QTreeView, position: QPoint):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    source_model, _proxy = _resolve_model(tree_view)
    if index.isValid():
        tree_view.setCurrentIndex(index)

    col = index.column()

    # Column 1 (type): behave like Enter on the type cell and pop the combobox.
    if col == 1:
        if _trigger_type_combo_from_context_menu(tree_view, index):
            return
        _add(context_menu, "Expand All", lambda: expand_all(tree_view))
        _add(context_menu, "Collapse All", lambda: collapse_all(tree_view))
        context_menu.exec(tree_view.mapToGlobal(position))
        return

    # ------------------------------------------------------------------
    # Capability flags driven by current selection
    # ------------------------------------------------------------------
    has_selection = source_model is not None and index.isValid()
    is_container = False
    can_sort_keys = False
    can_move_up = False
    can_move_down = False
    is_root = False

    if has_selection:
        source_index = _to_source_index(index)
        row0 = source_model.index(source_index.row(), 0, source_index.parent())
        item = source_model.get_item(row0)
        is_container = item.json_type in (JsonType.OBJECT, JsonType.ARRAY)
        can_sort_keys = item.json_type is JsonType.OBJECT
        can_move_up = row0.row() > 0
        can_move_down = row0.row() < source_model.rowCount(row0.parent()) - 1
        is_root = item is source_model.root_item

    clipboard_has = has_clipboard_entries()

    # ------------------------------------------------------------------
    # Edit group: copy / cut / delete / duplicate
    # ------------------------------------------------------------------
    if col == 0:
        copy_slot = lambda: copy_selection_with_name(tree_view)
    elif col == 2:
        copy_slot = lambda: copy_selection_value_only(tree_view)
    else:
        copy_slot = lambda: copy_selection(tree_view)

    _add(context_menu, "Copy", copy_slot, enabled=has_selection, shortcut="Ctrl+C")
    _add(
        context_menu,
        "Cut",
        lambda: cut_selection(tree_view),
        enabled=has_selection and not is_root,
        shortcut="Ctrl+X",
    )

    # ------------------------------------------------------------------
    # Paste submenu (placement-aware) + auto Paste shortcut
    # ------------------------------------------------------------------
    paste_menu = context_menu.addMenu("Paste")
    paste_menu.setEnabled(clipboard_has)
    _add(
        paste_menu,
        "Paste (auto)",
        lambda: paste_from_clipboard(tree_view),
        enabled=clipboard_has,
        shortcut="Ctrl+V",
    )
    paste_menu.addSeparator()
    _add(
        paste_menu,
        "Paste Before",
        lambda: paste_before(tree_view),
        enabled=clipboard_has and has_selection and not is_root,
    )
    _add(
        paste_menu,
        "Paste After",
        lambda: paste_after(tree_view),
        enabled=clipboard_has and has_selection and not is_root,
    )
    _add(
        paste_menu,
        "Paste as Child",
        lambda: paste_as_child(tree_view),
        enabled=clipboard_has and is_container,
    )
    paste_menu.addSeparator()
    _add(
        paste_menu,
        "Paste — Replace Value",
        lambda: paste_replace_value(tree_view),
        enabled=clipboard_has and has_selection and not is_root,
    )

    # ------------------------------------------------------------------
    # Insert submenu (fresh empty node) — three placements
    # ------------------------------------------------------------------
    insert_menu = context_menu.addMenu("Insert")
    _add(
        insert_menu,
        "Insert Before",
        lambda: insert_sibling_before(tree_view),
        enabled=has_selection and not is_root,
    )
    _add(
        insert_menu,
        "Insert After",
        lambda: insert_sibling_after(tree_view),
        enabled=has_selection and not is_root,
    )
    _add(
        insert_menu,
        "Insert as Child",
        lambda: insert_child_current(tree_view),
        enabled=is_container,
    )

    context_menu.addSeparator()

    _add(
        context_menu,
        "Duplicate",
        lambda: duplicate_selection(tree_view),
        enabled=has_selection and not is_root,
    )
    _add(
        context_menu,
        "Delete",
        lambda: delete_selection(tree_view),
        enabled=has_selection and not is_root,
        shortcut="Del",
    )

    context_menu.addSeparator()

    # ------------------------------------------------------------------
    # Arrange group: move / sort
    # ------------------------------------------------------------------
    _add(context_menu, "Move Up", lambda: move_selection_up(tree_view), enabled=can_move_up)
    _add(context_menu, "Move Down", lambda: move_selection_down(tree_view), enabled=can_move_down)
    _add(
        context_menu,
        "Sort Keys",
        lambda: sort_selection_keys(tree_view, recursive=False),
        enabled=can_sort_keys,
    )
    _add(
        context_menu,
        "Sort Keys (Recursive)",
        lambda: sort_selection_keys(tree_view, recursive=True),
        enabled=can_sort_keys,
    )

    context_menu.addSeparator()

    _add(context_menu, "Expand All", lambda: expand_all(tree_view))
    _add(context_menu, "Collapse All", lambda: collapse_all(tree_view))

    context_menu.exec(tree_view.mapToGlobal(position))
