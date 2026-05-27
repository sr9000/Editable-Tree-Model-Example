import time
from typing import Any

from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt
from PySide6.QtGui import QUndoCommand

from tree.item import JsonTreeItem
from tree.item_names import unique_child_name
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix

_CMD_ID_RENAME = 0x0E71_0001
_CMD_ID_EDIT_VALUE = 0x0E71_0002
_MERGE_WINDOW_SECONDS = 0.5


def _select_placed_rows(tab, placed: list[tuple[tuple, int]]) -> None:
    """Select every (parent_path, row) entry in the view after a move."""
    if not placed:
        return
    model = tab.data_store.model
    sm = tab.data_store.view.selectionModel()
    selection = QItemSelection()
    first_view_idx = None
    for parent_path, row in placed:
        p = tab.data_store.mutations.index_from_path(parent_path)
        src_idx = model.index(row, 0, p)
        view_idx = tab.data_store.mutations.source_to_view(src_idx)
        if view_idx.isValid():
            selection.select(view_idx, view_idx)
            if first_view_idx is None:
                first_view_idx = view_idx
    sm.select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    # Update current index WITHOUT touching the selection (NoUpdate keeps it intact).
    if first_view_idx is not None:
        sm.setCurrentIndex(first_view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)


class _MoveRowCmd(QUndoCommand):
    """Move a single row inside its parent. O(1) state: 3 ints."""

    def __init__(self, tab: "JsonTab", text: str, parent_path: tuple, src: int, dst: int):
        super().__init__(text)
        self._tab = tab
        self._parent_path = parent_path
        self._src = src
        self._dst = dst

    def redo(self):
        p = self._tab.data_store.mutations.index_from_path(self._parent_path)
        if self._tab.data_store.model.move_row(p, self._src, self._dst):
            source_index = self._tab.data_store.model.index(self._dst, 0, p)
            self._tab.data_store.view.setCurrentIndex(self._tab.data_store.mutations.source_to_view(source_index))

    def undo(self):
        p = self._tab.data_store.mutations.index_from_path(self._parent_path)
        if self._tab.data_store.model.move_row(p, self._dst, self._src):
            source_index = self._tab.data_store.model.index(self._src, 0, p)
            self._tab.data_store.view.setCurrentIndex(self._tab.data_store.mutations.source_to_view(source_index))


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
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if not idx.isValid():
            return
        item = self._tab.data_store.model.get_item(idx)
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
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if idx.isValid():
            self._tab._diff_apply(self._tab.data_store.model.get_item(idx), self._new_value, idx)

    def undo(self):
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if idx.isValid():
            self._tab._diff_apply(self._tab.data_store.model.get_item(idx), self._old_subtree, idx)


class _ChangeTypeCmd(QUndoCommand):
    """Change a row's type (column 1). Stores old subtree subset for undo."""

    def __init__(
        self,
        tab: "JsonTab",
        text: str,
        path: tuple,
        old_subtree: Any,
        old_explicit: bool,
        old_type: JsonType,
        new_type: JsonType,
    ):
        super().__init__(text)
        self._tab = tab
        self._path = path
        self._old_subtree = old_subtree
        self._old_explicit = old_explicit
        self._old_type = old_type
        self._new_type = new_type

    def redo(self):
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if not idx.isValid():
            return
        type_idx = self._tab.data_store.model.index(idx.row(), 1, idx.parent())
        if not self._tab.data_store.model.setData(type_idx, self._new_type, Qt.ItemDataRole.EditRole):
            return

        item = self._tab.data_store.model.get_item(idx)
        if not isinstance(item.value, NumberAffix) or item.value.affix:
            return
        if item.json_type in (JsonType.INTEGER_CURRENCY, JsonType.FLOAT_CURRENCY):
            kind = AffixKind.CURRENCY
        elif item.json_type in (JsonType.INTEGER_UNITS, JsonType.FLOAT_UNITS):
            kind = AffixKind.UNITS
        else:
            return

        mru = self._tab.data_store.affix_mru
        if mru is None:
            return
        mru_items = mru.items(kind)
        if not mru_items:
            return

        replacement = NumberAffix(
            kind=kind,
            affix=mru_items[0],
            space=item.value.space,
            number=item.value.number,
        )
        value_idx = self._tab.data_store.model.index(idx.row(), 2, idx.parent())
        self._tab.data_store.model.setData(value_idx, replacement, Qt.ItemDataRole.EditRole)

    def undo(self):
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if not idx.isValid():
            return
        type_idx = self._tab.data_store.model.index(idx.row(), 1, idx.parent())
        value_idx = self._tab.data_store.model.index(idx.row(), 2, idx.parent())
        self._tab.data_store.model.setData(type_idx, self._old_type, Qt.ItemDataRole.EditRole)
        self._tab.data_store.model.setData(value_idx, self._old_subtree, Qt.ItemDataRole.EditRole)
        item = self._tab.data_store.model.get_item(idx)
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
            p = self._tab.data_store.mutations.index_from_path(rec["parent_path"])
            parent_item = self._tab.data_store.model.get_item(p)
            self._tab._insert_typed_item(parent_item, p, rec["row"], rec["value"], name=rec.get("name"))
            if first_idx is None:
                first_idx = self._tab.data_store.model.index(rec["row"], 0, p)
        if self._set_current and first_idx is not None and first_idx.isValid():
            self._tab.data_store.view.setCurrentIndex(self._tab.data_store.mutations.source_to_view(first_idx))

    def undo(self):
        for rec in reversed(self._inserts):
            p = self._tab.data_store.mutations.index_from_path(rec["parent_path"])
            self._tab.data_store.model.removeRow(rec["row"], p)


class _RemoveRowsCmd(QUndoCommand):
    """Remove N rows with stored per-row parent_path/row/name/value payloads."""

    def __init__(self, tab: "JsonTab", text: str, removals: list):
        super().__init__(text)
        self._tab = tab
        self._removals = removals

    def redo(self):
        for rec in self._removals:
            p = self._tab.data_store.mutations.index_from_path(rec["parent_path"])
            self._tab.data_store.model.removeRow(rec["row"], p)

    def undo(self):
        for rec in reversed(self._removals):
            p = self._tab.data_store.mutations.index_from_path(rec["parent_path"])
            parent_item = self._tab.data_store.model.get_item(p)
            self._tab._insert_typed_item(parent_item, p, rec["row"], rec["value"], name=rec["name"])


class _MoveRowsCmd(QUndoCommand):
    """Move N rows (possibly cross-parent) as a single undo step.

    Anchor-based variant (Step 9). ``sources`` is a list of
    ``(parent_path, row)`` tuples captured *before* the command runs.
    ``anchor`` is a ``MoveAnchor`` that names the destination gap by
    reference to a non-moving sibling (or end-of-parent sentinel).

    Selection restore is **not** performed inside redo/undo; the
    action-layer caller reads ``placed_paths`` / ``source_paths`` and
    drives the selection model itself.

    Algorithm (redo):
    1. Sort sources descending by ``(parent_path, row)`` so each
       removal leaves the remaining source indexes valid.
    2. For each removed item, record the detached ``JsonTreeItem`` and
       its origin ``(parent_path, row)``.
    3. Resolve the anchor to a post-pop ``insert_row`` via
       ``resolve_anchor_insert_row`` (subtracts the count of removed
       siblings ahead of the anchor sibling in the same parent).
    4. Insert the detached items in original ascending order at the
       resolved insert row.
    """

    def __init__(
        self,
        tab: "JsonTab",
        text: str,
        sources: list[tuple[tuple, int]],
        source_names: list[Any] | None,
        anchor,
    ):
        super().__init__(text)
        self._tab = tab
        self._sources = sources  # list of (parent_path, row), original positions
        self._source_names = {src: name for src, name in zip(sources, source_names or [], strict=False)}
        self._anchor = anchor
        # Populated during redo; used by undo and by the post-hook to drive selection.
        self._placed: list[tuple[tuple, int]] = []

    def _original_name_for(self, source: tuple[tuple, int], item: object) -> Any:
        # item is a JsonTreeItem when called from the command lifecycle; the
        # ``object`` annotation is kept loose for forward-compat with redo
        # callbacks that may pass a placeholder before the model resolves it.
        fallback = item.name if isinstance(item, JsonTreeItem) else None
        return self._source_names.get(source, fallback)

    # ------------------------------------------------------------------
    # Public accessors — used by the action layer for post-redo hooks
    # ------------------------------------------------------------------

    @property
    def placed_paths(self) -> list[tuple[tuple, int]]:
        return list(self._placed)

    @property
    def source_paths(self) -> list[tuple[tuple, int]]:
        return list(self._sources)

    # ------------------------------------------------------------------
    # mergeWith: always False — every move is its own undo step
    # ------------------------------------------------------------------

    def mergeWith(self, _other: QUndoCommand) -> bool:  # type: ignore[override]
        return False

    # ------------------------------------------------------------------
    # redo / undo
    # ------------------------------------------------------------------

    def redo(self) -> None:
        from tree_actions.anchors import resolve_anchor_target

        tab = self._tab
        model = tab.data_store.model

        # 1. Descending source order: removals don't invalidate remaining sources.
        sorted_sources = sorted(self._sources, key=lambda p: (p[0], p[1]), reverse=True)

        detached: list[tuple[tuple, int, object]] = []
        for parent_path, row in sorted_sources:
            p = tab.data_store.mutations.index_from_path(parent_path)
            parent_item = model.get_item(p)
            item = parent_item.child_items[row]
            with model.rows_removal(p, row, 1):
                parent_item.child_items.pop(row)
                parent_item.mark_children_dirty()
            detached.append((parent_path, row, item))

        detached.reverse()  # restore ascending source order

        # 2. Resolve the anchor to the current (parent_path, insert_row) AFTER
        # removing sources. The anchor's parent path itself may have shifted
        # if any source sat in an ancestor at a lower row — without this
        # adjustment a drop onto a sibling that lives after the dragged
        # source(s) would land in the WRONG container.
        adjusted_parent_path, insert_row = resolve_anchor_target(model, tab, self._anchor, self._sources)
        t_parent = tab.data_store.mutations.index_from_path(adjusted_parent_path)
        t_parent_item = model.get_item(t_parent)
        used_names = {c.name for c in t_parent_item.child_items if isinstance(c.name, str)}

        # Clamp defensively (out-of-range insert rows should never reach here,
        # but list.insert silently clamps so guarding against drift is cheap).
        insert_row = max(0, min(insert_row, t_parent_item.child_count()))

        self._placed = []
        for offset, (sp, sr, item) in enumerate(detached):
            ins_row = insert_row + offset
            item.parent_item = t_parent_item
            original_name = self._original_name_for((sp, sr), item)
            if t_parent_item.json_type is JsonType.OBJECT:
                base = original_name.strip() if isinstance(original_name, str) and original_name.strip() else "new_key"
                item.name = unique_child_name(t_parent_item.child_items, base=base, used_names=used_names)
                used_names.add(item.name)
            else:
                item.name = original_name
            with model.rows_insertion(t_parent, ins_row, 1):
                t_parent_item.child_items.insert(ins_row, item)
                t_parent_item.mark_children_dirty()
            self._placed.append((adjusted_parent_path, ins_row))

    def undo(self) -> None:
        tab = self._tab
        model = tab.data_store.model

        if not self._placed:
            return

        sorted_placed = sorted(self._placed, key=lambda p: (p[0], p[1]), reverse=True)
        detached: list[object] = []
        for parent_path, row in sorted_placed:
            p = tab.data_store.mutations.index_from_path(parent_path)
            parent_item = model.get_item(p)
            item = parent_item.child_items[row]
            with model.rows_removal(p, row, 1):
                parent_item.child_items.pop(row)
                parent_item.mark_children_dirty()
            detached.append(item)

        detached.reverse()

        sorted_sources_asc = sorted(self._sources, key=lambda p: (p[0], p[1]))
        used_by_parent: dict[tuple, set[str]] = {}
        for (parent_path, row), item in zip(sorted_sources_asc, detached):
            p = tab.data_store.mutations.index_from_path(parent_path)
            parent_item = model.get_item(p)
            item.parent_item = parent_item
            original_name = self._original_name_for((parent_path, row), item)
            if parent_item.json_type is JsonType.OBJECT:
                used = used_by_parent.setdefault(
                    parent_path,
                    {c.name for c in parent_item.child_items if isinstance(c.name, str)},
                )
                if isinstance(original_name, str) and original_name.strip() and original_name not in used:
                    item.name = original_name
                else:
                    base = (
                        original_name.strip() if isinstance(original_name, str) and original_name.strip() else "new_key"
                    )
                    item.name = unique_child_name(parent_item.child_items, base=base, used_names=used)
                used.add(item.name)
            else:
                item.name = original_name
            with model.rows_insertion(p, row, 1):
                parent_item.child_items.insert(row, item)
                parent_item.mark_children_dirty()


class _SortKeysCmd(QUndoCommand):
    """Sort children of an OBJECT and store prior subtree subset for undo."""

    def __init__(self, tab: "JsonTab", text: str, path: tuple, old_subtree: Any, recursive: bool):
        super().__init__(text)
        self._tab = tab
        self._path = path
        self._old_subtree = old_subtree
        self._recursive = recursive

    def redo(self):
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if idx.isValid():
            self._tab.data_store.model.sort_keys(idx, recursive=self._recursive)

    def undo(self):
        idx = self._tab.data_store.mutations.index_from_path(self._path)
        if idx.isValid():
            self._tab._diff_apply(self._tab.data_store.model.get_item(idx), self._old_subtree, idx)


class _SwitchFieldCaseCmd(QUndoCommand):
    """Rename multiple object-field names as one undo step."""

    def __init__(self, tab: "JsonTab", text: str, renames: list[dict[str, Any]]):
        super().__init__(text)
        self._tab = tab
        self._renames = list(renames)

    def redo(self):
        self._apply("new_name")

    def undo(self):
        self._apply("old_name")

    def _apply(self, key: str) -> None:
        for rec in self._renames:
            idx = self._tab.data_store.mutations.index_from_path(rec["path"])
            if not idx.isValid():
                continue
            item = self._tab.data_store.model.get_item(idx)
            item.name = rec[key]
            if item.parent_item is not None:
                item.parent_item.mark_children_dirty()
            self._tab._emit_row_changed(idx)
