import time
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoCommand

from tree.types import JsonType

_CMD_ID_RENAME = 0x0E71_0001
_CMD_ID_EDIT_VALUE = 0x0E71_0002
_MERGE_WINDOW_SECONDS = 0.5


class _MoveRowCmd(QUndoCommand):
    """Move a single row inside its parent. O(1) state: 3 ints."""

    def __init__(self, tab: "JsonTab", text: str, parent_path: tuple, src: int, dst: int):
        super().__init__(text)
        self._tab = tab
        self._parent_path = parent_path
        self._src = src
        self._dst = dst

    def redo(self):
        p = self._tab._index_from_path(self._parent_path)
        if self._tab.model.move_row(p, self._src, self._dst):
            source_index = self._tab.model.index(self._dst, 0, p)
            self._tab.view.setCurrentIndex(self._tab._source_to_view(source_index))

    def undo(self):
        p = self._tab._index_from_path(self._parent_path)
        if self._tab.model.move_row(p, self._dst, self._src):
            source_index = self._tab.model.index(self._src, 0, p)
            self._tab.view.setCurrentIndex(self._tab._source_to_view(source_index))


class _RenameCmd(QUndoCommand):
    """Rename a row's name (column 0). O(1) state: 2 strings."""

    def __init__(self, tab: "JsonTab", text: str, path: tuple, old_name: Any, new_name: Any):
        super().__init__(text)
        self._tab = tab
        self._path = path
        self._old = old_name
        self._new = new_name
        self._timestamp = time.monotonic()

    def id(self) -> int:  # noqa: A003 - Qt API
        return _CMD_ID_RENAME

    def mergeWith(self, other: QUndoCommand) -> bool:  # type: ignore[override]
        if not isinstance(other, _RenameCmd):
            return False
        if other._path != self._path:
            return False
        if other._timestamp - self._timestamp > _MERGE_WINDOW_SECONDS:
            return False
        self._new = other._new
        self._timestamp = other._timestamp
        return True

    def redo(self):
        self._apply(self._new)

    def undo(self):
        self._apply(self._old)

    def _apply(self, name: Any) -> None:
        idx = self._tab._index_from_path(self._path)
        if not idx.isValid():
            return
        item = self._tab.model.get_item(idx)
        item.name = name
        if item.parent_item is not None:
            item.parent_item.mark_children_dirty()
        self._tab._emit_row_changed(idx)


class _EditValueCmd(QUndoCommand):
    """Edit a value cell. Stores the affected SUBTREE on each side."""

    def __init__(self, tab: "JsonTab", text: str, path: tuple, old_subtree: Any, new_value: Any):
        super().__init__(text)
        self._tab = tab
        self._path = path
        self._old_subtree = old_subtree
        self._new_value = new_value
        self._timestamp = time.monotonic()

    def id(self) -> int:  # noqa: A003 - Qt API
        return _CMD_ID_EDIT_VALUE

    def mergeWith(self, other: QUndoCommand) -> bool:  # type: ignore[override]
        if not isinstance(other, _EditValueCmd):
            return False
        if other._path != self._path:
            return False
        if other._timestamp - self._timestamp > _MERGE_WINDOW_SECONDS:
            return False
        self._new_value = other._new_value
        self._timestamp = other._timestamp
        return True

    def redo(self):
        idx = self._tab._index_from_path(self._path)
        if idx.isValid():
            self._tab._diff_apply(self._tab.model.get_item(idx), self._new_value, idx)

    def undo(self):
        idx = self._tab._index_from_path(self._path)
        if idx.isValid():
            self._tab._diff_apply(self._tab.model.get_item(idx), self._old_subtree, idx)


class _ChangeTypeCmd(QUndoCommand):
    """Change a row's type (column 1). Stores old subtree subset for undo."""

    def __init__(
        self,
        tab: "JsonTab",
        text: str,
        path: tuple,
        old_subtree: Any,
        old_explicit: bool,
        new_type: JsonType,
    ):
        super().__init__(text)
        self._tab = tab
        self._path = path
        self._old_subtree = old_subtree
        self._old_explicit = old_explicit
        self._new_type = new_type

    def redo(self):
        idx = self._tab._index_from_path(self._path)
        if not idx.isValid():
            return
        type_idx = self._tab.model.index(idx.row(), 1, idx.parent())
        self._tab.model.setData(type_idx, self._new_type, Qt.ItemDataRole.EditRole)

    def undo(self):
        idx = self._tab._index_from_path(self._path)
        if not idx.isValid():
            return
        item = self._tab.model.get_item(idx)
        self._tab._diff_apply(item, self._old_subtree, idx)
        item.explicit_type = self._old_explicit


class _InsertRowsCmd(QUndoCommand):
    """Insert N rows with stored per-row parent_path/row/value/name payloads."""

    def __init__(self, tab: "JsonTab", text: str, inserts: list, *, set_current_to_first: bool = True):
        super().__init__(text)
        self._tab = tab
        self._inserts = inserts
        self._set_current = set_current_to_first

    def redo(self):
        first_idx = None
        for rec in self._inserts:
            p = self._tab._index_from_path(rec["parent_path"])
            parent_item = self._tab.model.get_item(p)
            self._tab._insert_typed_item(parent_item, p, rec["row"], rec["value"], name=rec.get("name"))
            if first_idx is None:
                first_idx = self._tab.model.index(rec["row"], 0, p)
        if self._set_current and first_idx is not None and first_idx.isValid():
            self._tab.view.setCurrentIndex(self._tab._source_to_view(first_idx))

    def undo(self):
        for rec in reversed(self._inserts):
            p = self._tab._index_from_path(rec["parent_path"])
            self._tab.model.removeRow(rec["row"], p)


class _RemoveRowsCmd(QUndoCommand):
    """Remove N rows with stored per-row parent_path/row/name/value payloads."""

    def __init__(self, tab: "JsonTab", text: str, removals: list):
        super().__init__(text)
        self._tab = tab
        self._removals = removals

    def redo(self):
        for rec in self._removals:
            p = self._tab._index_from_path(rec["parent_path"])
            self._tab.model.removeRow(rec["row"], p)

    def undo(self):
        for rec in reversed(self._removals):
            p = self._tab._index_from_path(rec["parent_path"])
            parent_item = self._tab.model.get_item(p)
            self._tab._insert_typed_item(parent_item, p, rec["row"], rec["value"], name=rec["name"])


class _SortKeysCmd(QUndoCommand):
    """Sort children of an OBJECT and store prior subtree subset for undo."""

    def __init__(self, tab: "JsonTab", text: str, path: tuple, old_subtree: Any, recursive: bool):
        super().__init__(text)
        self._tab = tab
        self._path = path
        self._old_subtree = old_subtree
        self._recursive = recursive

    def redo(self):
        idx = self._tab._index_from_path(self._path)
        if idx.isValid():
            self._tab.model.sort_keys(idx, recursive=self._recursive)

    def undo(self):
        idx = self._tab._index_from_path(self._path)
        if idx.isValid():
            self._tab._diff_apply(self._tab.model.get_item(idx), self._old_subtree, idx)
