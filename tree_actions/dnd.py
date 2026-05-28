from __future__ import annotations

from PySide6.QtCore import QMimeData, QModelIndex, Qt

from tree.types import JsonType
from tree.view import JsonTreeView
from tree_actions._tab_lookup import find_owning_tab
from tree_actions.clipboard import MIME_JSON_TREE, entries_from_mime, source_paths_from_mime
from tree_actions.paste import paste_entries_at


def _tab_of(view):
    return find_owning_tab(view)


def _row0(model, index: QModelIndex) -> QModelIndex:
    if not index.isValid():
        return QModelIndex()
    return model.index(index.row(), 0, index.parent())


def _path_relative_to_root(model, index: QModelIndex) -> tuple[int, ...]:
    if not index.isValid():
        return ()
    root_item = model.root_item
    if model.get_item(index) is root_item:
        return ()
    path: list[int] = []
    cursor = index
    while cursor.isValid() and model.get_item(cursor) is not root_item:
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


def _resolve_drop_target(model, row: int, parent: QModelIndex) -> tuple[QModelIndex, int] | None:
    parent_row0 = _row0(model, parent)

    if row != -1:
        target_parent = parent_row0 if parent_row0.isValid() else QModelIndex()
        clamped = max(0, min(int(row), model.rowCount(target_parent)))
        return target_parent, clamped

    if not parent_row0.isValid():
        return QModelIndex(), model.rowCount(QModelIndex())

    parent_item = model.get_item(parent_row0)
    if parent_item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
        return parent_row0, model.rowCount(parent_row0)

    # Fallback for on-row drops over leaves: place after leaf sibling.
    return parent_row0.parent(), parent_row0.row() + 1


def can_drop(model, mime, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
    if action == Qt.DropAction.IgnoreAction:
        return False
    if action not in (Qt.DropAction.MoveAction, Qt.DropAction.CopyAction):
        return False
    if column not in (-1, 0):
        return False
    if mime is None:
        return False
    if not mime.hasFormat(MIME_JSON_TREE) and not (isinstance(mime, QMimeData) and mime.text().strip()):
        return False
    if not entries_from_mime(mime):
        return False

    source_paths = source_paths_from_mime(mime)
    if action == Qt.DropAction.MoveAction and not source_paths:
        # For MoveAction we need source paths to enforce cycle guards.
        return False

    target = _resolve_drop_target(model, row, parent)
    if target is None:
        return False

    if source_paths:
        target_parent, _target_row = target
        target_parent_path = _path_relative_to_root(model, target_parent)
        for src_path in source_paths:
            if target_parent_path[: len(src_path)] == src_path:
                return False
    return True


def _notify_drop(tab, action: Qt.DropAction, count: int, target_parent: QModelIndex) -> None:
    if tab is None:
        return
    noun = "row" if count == 1 else "rows"
    verb = "Copied" if action == Qt.DropAction.CopyAction else "Moved"
    target_name = tab._qualified_name(target_parent)
    tab.show_status(f"{verb} {count} {noun} under {target_name}", 2000)


def handle_drop(view, model, mime, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
    if not can_drop(model, mime, action, row, column, parent):
        return False

    target = _resolve_drop_target(model, row, parent)
    if target is None:
        return False
    target_parent, target_row = target

    tab = _tab_of(view)
    if tab is None:
        return False

    if action == Qt.DropAction.MoveAction:
        source_rows = model.consume_drag_source_rows()
        if source_rows:
            # Internal same-model move: let the tab perform the structural
            # change as a single undo step. Mark the originating view so its
            # overridden ``startDrag`` skips Qt's default post-drag
            # ``clearOrRemove`` (which would otherwise delete the freshly
            # placed destination rows — the "disappearing item" bug).
            moved = tab.data_store.mutations.push_move_rows(source_rows, target_parent, target_row, label="drag move")
            if moved and isinstance(view, JsonTreeView):
                view.mark_drag_handled_internally()
            if moved:
                _notify_drop(tab, action, len(source_rows), target_parent)
            return moved

    entries = entries_from_mime(mime)
    if not entries:
        return False
    copy_label = "drag copy" if action == Qt.DropAction.CopyAction else "drag drop"
    changed = paste_entries_at(view, target_parent, target_row, entries, label=copy_label)
    if changed:
        _notify_drop(tab, action, len(entries), target_parent)
    return changed
