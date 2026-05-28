"""View-state capture/restore helpers used by typed move-row undo commands.

Extracted from :class:`documents.tab.JsonTab` to keep that class focused on
widget wiring.  All functions take the owning ``JsonTab`` as their first
argument and operate via its tree model, proxy view, and data-store-owned
history controller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex

from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths
from tree_actions.selection import selected_source_rows
from undo.commands import _MoveRowsCmd

if TYPE_CHECKING:
    from documents.tab import JsonTab


def collect_expanded_paths(tab: JsonTab) -> list[tuple[int, ...]]:
    """Return paths of every currently expanded row.

    Kept around because a few tests (and any future view-state save/restore)
    want to enumerate expansion.  It is no longer part of any undo/redo path.
    """
    paths: list[tuple[int, ...]] = []

    def visit(parent_index: QModelIndex) -> None:
        for r in range(tab.data_store.model.rowCount(parent_index)):
            child = tab.data_store.model.index(r, 0, parent_index)
            if not child.isValid():
                continue
            view_child = tab._source_to_view(child)
            if tab.data_store.view.isExpanded(view_child):
                paths.append(tab._index_path(child))
                visit(child)

    visit(QModelIndex())
    return paths


def capture_move_view_state(tab: JsonTab, sources: list) -> dict[str, Any]:
    roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
    for idx in sources:
        row0 = tab.data_store.model.index(idx.row(), 0, idx.parent())
        if not row0.isValid():
            continue
        key = (tab._index_path(row0.parent()), row0.row())
        view_idx = tab._source_to_view(row0)
        roots_state[key] = {
            "expanded_root": bool(view_idx.isValid() and tab.data_store.view.isExpanded(view_idx)),
            "expanded_rel": list(iter_expanded_relative_paths(tab.data_store.view, row0)),
        }

    selected_paths = [tab._index_path(idx) for idx in selected_source_rows(tab.data_store.view) if idx.isValid()]
    current_src = tab._proxy_to_source(tab.data_store.view.currentIndex())
    if current_src.isValid():
        current_src = tab.data_store.model.index(current_src.row(), 0, current_src.parent())
    current_path = tab._index_path(current_src) if current_src.isValid() else None
    return {
        "roots": roots_state,
        "selection_before": selected_paths,
        "current_before": current_path,
    }


def sort_move_paths(paths: list[tuple[tuple[int, ...], int]]) -> list[tuple[tuple[int, ...], int]]:
    return sorted(paths, key=lambda p: (p[0], p[1]))


def _apply_relative_expansion_mapping(
    tab: JsonTab,
    source_roots: list[tuple[tuple[int, ...], int]],
    target_roots: list[tuple[tuple[int, ...], int]],
    roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]],
) -> None:
    ordered_sources = sort_move_paths(source_roots)
    for source_root, target_root in zip(ordered_sources, target_roots):
        state = roots_state.get(source_root)
        if state is None:
            continue
        target_parent_path, target_row = target_root
        target_parent = tab._index_from_path(target_parent_path)
        target_index = tab.data_store.model.index(target_row, 0, target_parent)
        if not target_index.isValid():
            continue
        target_view = tab._source_to_view(target_index)
        if target_view.isValid():
            tab.data_store.view.setExpanded(target_view, bool(state.get("expanded_root", False)))
        apply_expanded_relative_paths(tab.data_store.view, target_index, state.get("expanded_rel", []))


def _restore_selection_paths(
    tab: JsonTab,
    paths: list[tuple[int, ...]],
    current_path: tuple[int, ...] | None,
) -> None:
    sm = tab.data_store.view.selectionModel()
    if sm is None:
        return
    selection = QItemSelection()
    first_view_idx = None
    for path in paths:
        src_idx = tab._index_from_path(path)
        view_idx = tab._source_to_view(src_idx)
        if not view_idx.isValid():
            continue
        selection.select(view_idx, view_idx)
        if first_view_idx is None:
            first_view_idx = view_idx
    sm.select(
        selection,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    if current_path is not None:
        src_current = tab._index_from_path(current_path)
        view_current = tab._source_to_view(src_current)
        if view_current.isValid():
            sm.setCurrentIndex(view_current, QItemSelectionModel.SelectionFlag.NoUpdate)
            return
    if first_view_idx is not None:
        sm.setCurrentIndex(first_view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)


def restore_selection_at_paths(tab: JsonTab, placed: list[tuple[tuple, int]]) -> None:
    """Drive the view's selectionModel so the rows at the given
    ``(parent_path, row)`` tuples are all selected after a move.

    Lifted out of ``_MoveRowsCmd`` so that the undo command stays decoupled
    from the view.
    """
    if not placed:
        return
    sm = tab.data_store.view.selectionModel()
    if sm is None:
        return
    selection = QItemSelection()
    first_view_idx = None
    for parent_path, row in placed:
        p = tab._index_from_path(parent_path)
        src_idx = tab.data_store.model.index(row, 0, p)
        view_idx = tab._source_to_view(src_idx)
        if view_idx.isValid():
            selection.select(view_idx, view_idx)
            if first_view_idx is None:
                first_view_idx = view_idx
    sm.select(
        selection,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    if first_view_idx is not None:
        sm.setCurrentIndex(first_view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)


def apply_move_view_state(tab: JsonTab, cmd: _MoveRowsCmd, *, undo: bool) -> None:
    state = tab.data_store._move_view_state_by_cmd_id.get(id(cmd))
    if state is None:
        return
    roots_state = state.get("roots", {})
    if undo:
        _apply_relative_expansion_mapping(tab, cmd.source_paths, sort_move_paths(cmd.source_paths), roots_state)
        _restore_selection_paths(tab, state.get("selection_before", []), state.get("current_before"))
        return
    _apply_relative_expansion_mapping(tab, cmd.source_paths, cmd.placed_paths, roots_state)
    restore_selection_at_paths(tab, cmd.placed_paths)


def on_undo_index_changed(tab: JsonTab, new_index: int) -> None:
    old_index = tab.data_store._last_undo_index
    if new_index == old_index:
        return

    if new_index > old_index:
        for i in range(old_index, new_index):
            cmd = tab.data_store.undo_stack.command(i)
            if isinstance(cmd, _MoveRowsCmd) and id(cmd) in tab.data_store._move_view_state_by_cmd_id:
                apply_move_view_state(tab, cmd, undo=False)
    else:
        for i in range(old_index - 1, new_index - 1, -1):
            cmd = tab.data_store.undo_stack.command(i)
            if isinstance(cmd, _MoveRowsCmd) and id(cmd) in tab.data_store._move_view_state_by_cmd_id:
                apply_move_view_state(tab, cmd, undo=True)
    tab.data_store._last_undo_index = new_index
