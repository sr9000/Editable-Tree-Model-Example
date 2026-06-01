from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QPoint, Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QComboBox, QFileDialog, QMenu, QMessageBox, QTreeView

from state.edit_limits import get_attach_file_warning_limit_bytes
from tree.codecs.bytes_codec import decode_bytes, encode_bytes
from tree.types import JsonType
from tree_actions._tab_lookup import find_owning_tab
from tree_actions.clipboard import copy_selection, copy_selection_value_only, copy_selection_with_name
from tree_actions.field_case import FIELD_CASE_LABELS, FIELD_CASE_ORDER
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
    collapse_selection_recursive,
    cut_selection,
    delete_selection,
    duplicate_selection,
    expand_selection_recursive,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_out_down,
    move_selection_out_up,
    move_selection_up,
    sort_selection_keys,
    switch_selection_case,
)

_BASE64_TYPES = {JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP}


def _add(menu: QMenu, text: str, slot, *, enabled: bool = True, shortcut: str | None = None):
    if not enabled:
        return None
    act = menu.addAction(text)
    if shortcut is not None:
        act.setShortcut(QKeySequence(shortcut))
    act.setEnabled(enabled)
    act.triggered.connect(slot)
    return act


def _find_enter_edit_target(host) -> object | None:
    return find_owning_tab(host)


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
        tab.edit_name_or_value_from_enter()
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
    if tab is not None:
        tab.show_status(text, timeout_ms)


def _search_is_active(tree_view: QTreeView) -> bool:
    tab = _find_enter_edit_target(tree_view)
    if tab is None:
        return False
    return bool(tab.search_edit.text().strip())


def _goto_row_and_clear_search(tree_view: QTreeView, clicked_index) -> bool:
    source_model, _proxy = _resolve_model(tree_view)
    if source_model is None or not clicked_index.isValid():
        return False

    source_index = _to_source_index(clicked_index)
    if not source_index.isValid():
        return False
    source_row = _row0(source_model, source_index)
    if not source_row.isValid():
        return False
    source_path = _index_path(source_row)
    target_col = max(0, min(2, int(source_index.column())))

    tab = _find_enter_edit_target(tree_view)
    if tab is None:
        return False

    search_edit = tab.search_edit

    if search_edit.text():
        search_edit.clear()
        tab.view_controller.apply_filter()

    idx = tab.mutations.index_from_path(source_path)
    if not idx.isValid():
        return False
    source_target = idx.siblingAtColumn(target_col)
    if not source_target.isValid():
        source_target = idx.siblingAtColumn(0)
    view_target = tab.mutations.source_to_view(source_target)
    if not view_target.isValid():
        return False

    parent = view_target.parent()
    while parent.isValid():
        tree_view.expand(parent)
        parent = parent.parent()

    tree_view.scrollTo(view_target)
    sm = tree_view.selectionModel()
    if sm is not None:
        sm.select(
            view_target,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )
        sm.setCurrentIndex(view_target, QItemSelectionModel.SelectionFlag.NoUpdate)
    return True


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


def _add_switch_case_submenu(menu: QMenu, title: str, tree_view: QTreeView, *, recursive: bool, enabled: bool) -> None:
    if not enabled:
        return
    sub = menu.addMenu(title)
    sub.setEnabled(enabled)
    for case_style in FIELD_CASE_ORDER:
        _add(
            sub,
            FIELD_CASE_LABELS[case_style],
            lambda _checked=False, s=case_style: switch_selection_case(tree_view, s, recursive=recursive),
            enabled=enabled,
        )


def _warn_large_open_file(tree_view: QTreeView, path: Path) -> bool:
    warning_limit = get_attach_file_warning_limit_bytes()
    try:
        size = path.stat().st_size
    except OSError as exc:
        _status_message(tree_view, f"Open failed: {exc}", 4000)
        QMessageBox.warning(tree_view, "Open failed", f"Could not read file size for:\n{path}\n\n{exc}")
        return False

    if size <= warning_limit:
        return True

    size_kb = size / 1024
    limit_kb = warning_limit / 1024
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
    if tab is not None:
        return bool(tab.mutations.commit_set_data(value_index, value, Qt.ItemDataRole.EditRole))
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
        return None

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
                # Root is available for sort keys if it is an OBJECT.
                if item.json_type is JsonType.OBJECT:
                    can_sort_keys = True
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
        "Go To",
        lambda _checked=False, idx=index: _goto_row_and_clear_search(tree_view, idx),
        enabled=_search_is_active(tree_view) and index.isValid(),
    )
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
    _add(context_menu, "Save as...", lambda: save_base64_as_file(tree_view), enabled=base64_value_index is not None)

    # ------------------------------------------------------------------
    # Paste submenu (placement-aware) + auto Paste shortcut
    # ------------------------------------------------------------------
    if clipboard_has:
        paste_menu = context_menu.addMenu("Paste")
        top_actions = 0
        placement_actions = 0
        _a = _add(paste_menu, "Paste (auto)", lambda: paste_auto(tree_view), enabled=True, shortcut="Ctrl+V")
        top_actions += int(_a is not None)
        _a = _add(
            paste_menu,
            "Paste at All Selected",
            lambda: paste_clones_at_targets(tree_view),
            enabled=selection_count > 1,
        )
        top_actions += int(_a is not None)
        _a = _add(
            paste_menu,
            "Paste Each After Selected",
            lambda: paste_insert_after_zip(tree_view),
            enabled=selection_count > 1,
            shortcut="Ctrl+Shift+V",
        )
        top_actions += int(_a is not None)
        _a = _add(
            paste_menu,
            "Replace Each Selected Value",
            lambda: paste_replace_zip(tree_view),
            enabled=selection_count > 1,
            shortcut="Ctrl+Alt+V",
        )
        top_actions += int(_a is not None)

        _a = _add(paste_menu, "Paste Before", lambda: paste_before(tree_view), enabled=has_non_root)
        placement_actions += int(_a is not None)
        _a = _add(paste_menu, "Paste After", lambda: paste_after(tree_view), enabled=has_non_root)
        placement_actions += int(_a is not None)
        _a = _add(paste_menu, "Paste as Child", lambda: paste_as_child(tree_view), enabled=is_container)
        placement_actions += int(_a is not None)
        _replace = _add(
            paste_menu,
            "Paste — Replace Value",
            lambda: paste_replace_value(tree_view),
            enabled=has_non_root,
        )
        if top_actions and (placement_actions or _replace is not None):
            paste_menu.insertSeparator(paste_menu.actions()[top_actions])
        if placement_actions and _replace is not None:
            paste_menu.addSeparator()

    # ------------------------------------------------------------------
    # Insert submenu (fresh empty node) — three placements
    # ------------------------------------------------------------------
    if has_non_root or can_insert_child:
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
        _add(insert_menu, "Insert as Child", lambda: insert_child_current(tree_view), enabled=can_insert_child)

    if context_menu.actions():
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

    if context_menu.actions() and context_menu.actions()[-1].isSeparator() is False:
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
    _add(context_menu, "Expand Recursively", lambda: expand_selection_recursive(tree_view), enabled=has_selection)
    _add(context_menu, "Collapse Recursively", lambda: collapse_selection_recursive(tree_view), enabled=has_selection)
    _add_switch_case_submenu(
        context_menu,
        "Switch Case",
        tree_view,
        recursive=False,
        enabled=has_selection,
    )
    _add_switch_case_submenu(
        context_menu,
        "Switch Case (Recursive)",
        tree_view,
        recursive=True,
        enabled=has_selection,
    )

    while context_menu.actions() and context_menu.actions()[-1].isSeparator():
        context_menu.removeAction(context_menu.actions()[-1])

    if execute and context_menu.actions():
        context_menu.exec(tree_view.mapToGlobal(position))
    return context_menu
