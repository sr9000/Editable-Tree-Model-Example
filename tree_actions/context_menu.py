from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QComboBox, QFileDialog, QMenu, QMessageBox, QTreeView

from delegates.bytes_codec import decode_bytes, encode_bytes
from settings import BINARY_ATTACH_WARNING_LIMIT_BYTES
from tree.types import JsonType
from tree_actions.clipboard import copy_selection, copy_selection_value_only, copy_selection_with_name
from tree_actions.paste import (
    has_clipboard_entries,
    paste_after,
    paste_as_child,
    paste_auto,
    paste_before,
    paste_clones_at_targets,
    paste_insert_after_zip,
    paste_replace_value,
    paste_replace_zip,
)
from tree_actions.selection import _index_path, _resolve_model, _row0, _to_source_index, selected_source_rows
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
    move_selection_out_down,
    move_selection_out_up,
    move_selection_up,
    sort_selection_keys,
)

_BASE64_TYPES = {JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP}
_LARGE_OPEN_WARNING_THRESHOLD = BINARY_ATTACH_WARNING_LIMIT_BYTES


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


def _clicked_row_is_selected(tree_view: QTreeView, index) -> bool:
    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None or not index.isValid():
        return False
    source_index = _to_source_index(index)
    if not source_index.isValid():
        return False
    clicked_row = _row0(source_model, source_index)
    if not clicked_row.isValid():
        return False
    clicked_path = _index_path(clicked_row)
    for row in selected_source_rows(tree_view):
        if not row.isValid():
            continue
        if _index_path(_row0(source_model, row)) == clicked_path:
            return True
    return False


def _prepare_context_selection(tree_view: QTreeView, index) -> None:
    """Keep multi-selection when right-clicking inside it; otherwise select the
    clicked row (legacy behavior)."""
    if not index.isValid():
        return
    sm = tree_view.selectionModel()
    if sm is None:
        return
    if _clicked_row_is_selected(tree_view, index):
        sm.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
        return
    sm.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)


def _status_message(tree_view: QTreeView, text: str, timeout_ms: int = 3000) -> None:
    tab = _find_enter_edit_target(tree_view)
    cb = getattr(tab, "_status_message_callback", None) if tab is not None else None
    if cb is not None:
        cb(text, timeout_ms)


def _selected_base64_value_index(tree_view: QTreeView):
    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None:
        return None
    rows = [idx for idx in selected_source_rows(tree_view) if idx.isValid()]
    if len(rows) != 1:
        return None
    row0 = _row0(source_model, rows[0])
    item = source_model.get_item(row0)
    if item is source_model.root_item or item.json_type not in _BASE64_TYPES:
        return None
    return row0.siblingAtColumn(2)


def _warn_large_open_file(tree_view: QTreeView, path: Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError as exc:
        _status_message(tree_view, f"Open failed: {exc}", 4000)
        QMessageBox.warning(tree_view, "Open failed", f"Could not read file size for:\n{path}\n\n{exc}")
        return False

    if size <= _LARGE_OPEN_WARNING_THRESHOLD:
        return True

    size_kb = size / 1024
    limit_kb = _LARGE_OPEN_WARNING_THRESHOLD / 1024
    answer = QMessageBox.warning(
        tree_view,
        "Large file warning",
        f"Selected file is {size_kb:.1f} KB (limit: {limit_kb:.0f} KB).\\nContinue importing?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def _set_value_from_context(tree_view: QTreeView, value_index, value: str) -> bool:
    if not value_index.isValid():
        return False
    tab = _find_enter_edit_target(tree_view)
    if tab is not None and hasattr(tab, "commit_set_data"):
        return bool(tab.commit_set_data(value_index, value, Qt.ItemDataRole.EditRole))
    model = value_index.model()
    if model is None:
        return False
    return bool(model.setData(value_index, value, Qt.ItemDataRole.EditRole))


def attach_base64_from_file(tree_view: QTreeView) -> bool:
    value_index = _selected_base64_value_index(tree_view)
    if value_index is None or not value_index.isValid():
        return False

    file_path, _selected_filter = QFileDialog.getOpenFileName(tree_view, "Attach from file")
    if not file_path:
        return False
    path = Path(file_path)
    if not _warn_large_open_file(tree_view, path):
        return False

    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None:
        return False
    row0 = _row0(source_model, value_index)
    item = source_model.get_item(row0)

    try:
        raw = path.read_bytes()
        encoded = encode_bytes(raw, item.json_type)
    except OSError as exc:
        _status_message(tree_view, f"Attach failed: {exc}", 4000)
        QMessageBox.warning(tree_view, "Attach failed", f"Could not open file:\n{path}\n\n{exc}")
        return False

    ok = _set_value_from_context(tree_view, value_index, encoded)
    if ok:
        _status_message(tree_view, f"Attached file: {path.name}", 2000)
    return ok


def save_base64_as_file(tree_view: QTreeView) -> bool:
    value_index = _selected_base64_value_index(tree_view)
    if value_index is None or not value_index.isValid():
        return False

    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None:
        return False
    row0 = _row0(source_model, value_index)
    item = source_model.get_item(row0)

    file_path, _selected_filter = QFileDialog.getSaveFileName(tree_view, "Save binary as")
    if not file_path:
        return False
    path = Path(file_path)

    try:
        raw = decode_bytes(item.value, item.json_type)
        path.write_bytes(raw)
    except Exception as exc:
        _status_message(tree_view, f"Save failed: {exc}", 4000)
        QMessageBox.warning(tree_view, "Save failed", f"Could not save file:\n{path}\n\n{exc}")
        return False

    _status_message(tree_view, f"Saved file: {path.name}", 2000)
    return True


def show_context_menu(tree_view: QTreeView, position: QPoint, *, execute: bool = True):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    source_model, _proxy = _resolve_model(tree_view)
    _prepare_context_selection(tree_view, index)

    col = index.column()

    # Column 1 (type): behave like Enter on the type cell and pop the combobox.
    if col == 1:
        if _trigger_type_combo_from_context_menu(tree_view, index):
            return
        _add(context_menu, "Expand All", lambda: expand_all(tree_view))
        _add(context_menu, "Collapse All", lambda: collapse_all(tree_view))
        if execute:
            context_menu.exec(tree_view.mapToGlobal(position))
        return context_menu

    # ------------------------------------------------------------------
    # Capability flags driven by current selection
    # ------------------------------------------------------------------
    selected_rows = (
        [idx for idx in selected_source_rows(tree_view) if idx.isValid()] if source_model is not None else []
    )
    has_selection = bool(selected_rows)
    selection_count = len(selected_rows)
    is_container = False
    can_sort_keys = False
    can_move_up = False
    can_move_down = False
    can_move_out = False
    has_non_root = False
    can_insert_child = False

    if has_selection:
        assert source_model is not None
        for row in selected_rows:
            row0 = _row0(source_model, row)
            item = source_model.get_item(row0)
            if item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
                can_insert_child = True
            if item is source_model.root_item:
                continue
            has_non_root = True
            is_container = is_container or item.json_type in (JsonType.OBJECT, JsonType.ARRAY)
            can_sort_keys = can_sort_keys or item.json_type is JsonType.OBJECT
            parent_index = row0.parent()
            if parent_index.isValid() and source_model.get_item(parent_index) is not source_model.root_item:
                can_move_out = True
        can_move_up = has_non_root
        can_move_down = has_non_root

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
        enabled=has_non_root,
        shortcut="Ctrl+X",
    )

    base64_value_index = _selected_base64_value_index(tree_view)
    _add(
        context_menu,
        "Attach from...",
        lambda: attach_base64_from_file(tree_view),
        enabled=base64_value_index is not None,
    )
    _add(
        context_menu,
        "Save as...",
        lambda: save_base64_as_file(tree_view),
        enabled=base64_value_index is not None,
    )

    # ------------------------------------------------------------------
    # Paste submenu (placement-aware) + auto Paste shortcut
    # ------------------------------------------------------------------
    paste_menu = context_menu.addMenu("Paste")
    paste_menu.setEnabled(clipboard_has)
    _add(
        paste_menu,
        "Paste (auto)",
        lambda: paste_auto(tree_view),
        enabled=clipboard_has,
        shortcut="Ctrl+V",
    )
    _add(
        paste_menu,
        "Paste at All Selected",
        lambda: paste_clones_at_targets(tree_view),
        enabled=clipboard_has and selection_count > 1,
    )
    _add(
        paste_menu,
        "Paste Each After Selected",
        lambda: paste_insert_after_zip(tree_view),
        enabled=clipboard_has and selection_count > 1,
        shortcut="Ctrl+Shift+V",
    )
    _add(
        paste_menu,
        "Replace Each Selected Value",
        lambda: paste_replace_zip(tree_view),
        enabled=clipboard_has and selection_count > 1,
        shortcut="Ctrl+Alt+V",
    )
    paste_menu.addSeparator()
    _add(
        paste_menu,
        "Paste Before",
        lambda: paste_before(tree_view),
        enabled=clipboard_has and has_non_root,
    )
    _add(
        paste_menu,
        "Paste After",
        lambda: paste_after(tree_view),
        enabled=clipboard_has and has_non_root,
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
        enabled=clipboard_has and has_non_root,
    )

    # ------------------------------------------------------------------
    # Insert submenu (fresh empty node) — three placements
    # ------------------------------------------------------------------
    insert_menu = context_menu.addMenu("Insert")
    _add(
        insert_menu,
        "Insert Before",
        lambda: insert_sibling_before(tree_view),
        enabled=has_non_root,
        shortcut="Ctrl+I",
    )
    _add(
        insert_menu,
        "Insert After",
        lambda: insert_sibling_after(tree_view),
        enabled=has_non_root,
        shortcut="Ctrl+Shift+I",
    )
    _add(
        insert_menu,
        "Insert as Child",
        lambda: insert_child_current(tree_view),
        enabled=can_insert_child,
    )

    context_menu.addSeparator()

    _add(
        context_menu,
        "Duplicate",
        lambda: duplicate_selection(tree_view),
        enabled=has_non_root,
        shortcut="Ctrl+D",
    )
    _add(
        context_menu,
        "Delete",
        lambda: delete_selection(tree_view),
        enabled=has_non_root,
        shortcut="Del",
    )

    context_menu.addSeparator()

    # ------------------------------------------------------------------
    # Arrange group: move / sort
    # ------------------------------------------------------------------
    _add(context_menu, "Move Up", lambda: move_selection_up(tree_view), enabled=can_move_up, shortcut="Alt+Up")
    _add(context_menu, "Move Down", lambda: move_selection_down(tree_view), enabled=can_move_down, shortcut="Alt+Down")
    _add(
        context_menu,
        "Move Out of Parent (Up)",
        lambda: move_selection_out_up(tree_view),
        enabled=can_move_out,
        shortcut="Ctrl+Alt+Up",
    )
    _add(
        context_menu,
        "Move Out of Parent (Down)",
        lambda: move_selection_out_down(tree_view),
        enabled=can_move_out,
        shortcut="Ctrl+Alt+Down",
    )
    _add(
        context_menu,
        "Sort Keys",
        lambda: sort_selection_keys(tree_view, recursive=False),
        enabled=can_sort_keys,
        shortcut="Ctrl+Alt+S",
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

    if execute:
        context_menu.exec(tree_view.mapToGlobal(position))
    return context_menu
