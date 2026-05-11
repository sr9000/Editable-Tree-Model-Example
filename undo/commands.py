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


class _MoveRowsCmd(QUndoCommand):
    """Move N rows (possibly cross-parent) as a single undo step.

    ``sources`` is a list of ``(parent_path, row)`` tuples that have been
    snapshot-captured *before* the command is executed (i.e. the tab already
    converted live ``QModelIndex`` values to paths).  ``target_parent_path``
    and ``target_row`` describe where the block lands after the move.

    Algorithm (redo):
    1. Sort sources in *descending* order so each ``removeRow`` leaves the
       remaining source indexes valid.
    2. For each removed item, record the detached ``JsonTreeItem`` and its
       origin ``(parent_path, row)`` so undo can replay in reverse.
    3. Adjust ``target_row`` downward by the number of removed siblings that
       were *ahead* of the target inside the *same* parent – identical to
       Qt's own drag-move convention.
    4. Insert the detached items (in original ascending order) at the
       adjusted target row, emitting the required model signals.
    """

    def __init__(
        self,
        tab: "JsonTab",
        text: str,
        sources: list[tuple[tuple, int]],
        target_parent_path: tuple,
        target_row: int,
    ):
        super().__init__(text)
        self._tab = tab
        self._sources = sources  # list of (parent_path, row)
        self._target_parent_path = target_parent_path
        self._target_row = target_row
        # Populated during first redo; used by undo to rebuild the inverse.
        self._placed: list[tuple[tuple, int]] = []  # (parent_path, row) after redo

    # ------------------------------------------------------------------
    # mergeWith: always False — every move is its own undo step
    # ------------------------------------------------------------------

    def mergeWith(self, _other: QUndoCommand) -> bool:  # type: ignore[override]
        return False

    # ------------------------------------------------------------------
    # redo / undo
    # ------------------------------------------------------------------

    def redo(self) -> None:
        tab = self._tab
        model = tab.model

        # 1. Sort sources descending so removal doesn't shift remaining sources.
        sorted_sources = sorted(self._sources, key=lambda p: (p[0], p[1]), reverse=True)

        # Snapshot the items before touching the model.
        detached: list[tuple[tuple, int, object]] = []  # (parent_path, row, item)
        for parent_path, row in sorted_sources:
            p = tab._index_from_path(parent_path)
            parent_item = model.get_item(p)
            item = parent_item.child_items[row]
            with model.rows_removal(p, row, 1):
                parent_item.child_items.pop(row)
                parent_item.mark_children_dirty()
            detached.append((parent_path, row, item))

        # 2. Re-order detached back to ascending source order (they were removed
        #    descending; reverse to restore original relative order).
        detached.reverse()

        # 3. Compute adjusted target row.
        target_row = self._target_row
        t_parent = tab._index_from_path(self._target_parent_path)
        for parent_path, row, _item in detached:
            if parent_path == self._target_parent_path and row < target_row:
                target_row -= 1

        # 4. Insert at target.
        t_parent_item = model.get_item(t_parent)
        t_parent_item._mark_for_insert = True  # sentinel — not used, see below
        self._placed = []
        for offset, (_src_parent_path, _src_row, item) in enumerate(detached):
            ins_row = target_row + offset
            item.parent_item = t_parent_item
            with model.rows_insertion(t_parent, ins_row, 1):
                t_parent_item.child_items.insert(ins_row, item)
                t_parent_item.mark_children_dirty()
            self._placed.append((self._target_parent_path, ins_row))

        # Update current index to first placed item.
        if self._placed:
            first_path, first_row = self._placed[0]
            p = tab._index_from_path(first_path)
            tab.view.setCurrentIndex(tab._source_to_view(model.index(first_row, 0, p)))

    def undo(self) -> None:
        tab = self._tab
        model = tab.model

        if not self._placed:
            return

        # Remove placed items in descending order.
        sorted_placed = sorted(self._placed, key=lambda p: (p[0], p[1]), reverse=True)
        detached: list[object] = []
        for parent_path, row in sorted_placed:
            p = tab._index_from_path(parent_path)
            parent_item = model.get_item(p)
            item = parent_item.child_items[row]
            with model.rows_removal(p, row, 1):
                parent_item.child_items.pop(row)
                parent_item.mark_children_dirty()
            detached.append(item)

        # Reverse to restore original order (we removed descending, reverse → ascending).
        detached.reverse()

        # Re-insert at original source positions in ascending order.
        sorted_sources_asc = sorted(self._sources, key=lambda p: (p[0], p[1]))
        first_restored = None
        for (parent_path, row), item in zip(sorted_sources_asc, detached):
            p = tab._index_from_path(parent_path)
            parent_item = model.get_item(p)
            item.parent_item = parent_item
            with model.rows_insertion(p, row, 1):
                parent_item.child_items.insert(row, item)
                parent_item.mark_children_dirty()
            if first_restored is None:
                first_restored = (parent_path, row)

        if first_restored is not None:
            fp, fr = first_restored
            p = tab._index_from_path(fp)
            tab.view.setCurrentIndex(tab._source_to_view(model.index(fr, 0, p)))


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
