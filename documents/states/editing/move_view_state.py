"""Move/drag view-state capture and restoration helpers."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex

from documents.states.editing.context import EditingContext
from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths
from tree_actions.selection import selected_source_rows
from undo.commands import _MoveRowsCmd


class MoveViewState:
    """Capture and restore expansion/selection around move-row commands."""

    def __init__(self, context: EditingContext) -> None:
        self._context = context

    def collect_expanded_paths(self) -> list[tuple[int, ...]]:
        """Return paths of every currently expanded row."""
        tab = self._context.tab
        paths: list[tuple[int, ...]] = []

        def visit(parent_index: QModelIndex) -> None:
            for r in range(tab.model.rowCount(parent_index)):
                child = tab.model.index(r, 0, parent_index)
                if not child.isValid():
                    continue
                view_child = tab.view_controller.source_to_view(child)
                if tab.view_state.view.isExpanded(view_child):
                    paths.append(tab.view_controller.index_path(child))
                    visit(child)

        visit(QModelIndex())
        return paths

    def capture_move_view_state(self, sources: list) -> dict[str, Any]:
        tab = self._context.tab
        roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
        for idx in sources:
            row0 = tab.model.index(idx.row(), 0, idx.parent())
            if not row0.isValid():
                continue
            key = (tab.view_controller.index_path(row0.parent()), row0.row())
            view_idx = tab.view_controller.source_to_view(row0)
            roots_state[key] = {
                "expanded_root": bool(view_idx.isValid() and tab.view_state.view.isExpanded(view_idx)),
                "expanded_rel": list(iter_expanded_relative_paths(tab.view_state.view, row0)),
            }

        selected_paths = [
            tab.view_controller.index_path(idx) for idx in selected_source_rows(tab.view_state.view) if idx.isValid()
        ]
        current_src = tab.view_controller.proxy_to_source(tab.view_state.view.currentIndex())
        if current_src.isValid():
            current_src = tab.model.index(current_src.row(), 0, current_src.parent())
        current_path = tab.view_controller.index_path(current_src) if current_src.isValid() else None
        return {
            "roots": roots_state,
            "selection_before": selected_paths,
            "current_before": current_path,
        }

    @staticmethod
    def sort_move_paths(paths: list[tuple[tuple[int, ...], int]]) -> list[tuple[tuple[int, ...], int]]:
        return sorted(paths, key=lambda p: (p[0], p[1]))

    def _apply_relative_expansion_mapping(
        self,
        source_roots: list[tuple[tuple[int, ...], int]],
        target_roots: list[tuple[tuple[int, ...], int]],
        roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]],
    ) -> None:
        tab = self._context.tab
        ordered_sources = self.sort_move_paths(source_roots)
        for source_root, target_root in zip(ordered_sources, target_roots):
            state = roots_state.get(source_root)
            if state is None:
                continue
            target_parent_path, target_row = target_root
            target_parent = tab.view_controller.index_from_path(target_parent_path)
            target_index = tab.model.index(target_row, 0, target_parent)
            if not target_index.isValid():
                continue
            target_view = tab.view_controller.source_to_view(target_index)
            if target_view.isValid():
                tab.view_state.view.setExpanded(target_view, bool(state.get("expanded_root", False)))
            apply_expanded_relative_paths(tab.view_state.view, target_index, state.get("expanded_rel", []))

    def _restore_selection_paths(
        self,
        paths: list[tuple[int, ...]],
        current_path: tuple[int, ...] | None,
    ) -> None:
        tab = self._context.tab
        sm = tab.view_state.view.selectionModel()
        if sm is None:
            return
        selection = QItemSelection()
        first_view_idx = None
        for path in paths:
            src_idx = tab.view_controller.index_from_path(path)
            view_idx = tab.view_controller.source_to_view(src_idx)
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
            src_current = tab.view_controller.index_from_path(current_path)
            view_current = tab.view_controller.source_to_view(src_current)
            if view_current.isValid():
                sm.setCurrentIndex(view_current, QItemSelectionModel.SelectionFlag.NoUpdate)
                return
        if first_view_idx is not None:
            sm.setCurrentIndex(first_view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)

    def restore_selection_at_paths(self, placed: list[tuple[tuple, int]]) -> None:
        """Select the rows at the given ``(parent_path, row)`` tuples."""
        tab = self._context.tab
        if not placed:
            return
        sm = tab.view_state.view.selectionModel()
        if sm is None:
            return
        selection = QItemSelection()
        first_view_idx = None
        for parent_path, row in placed:
            p = tab.view_controller.index_from_path(parent_path)
            src_idx = tab.model.index(row, 0, p)
            view_idx = tab.view_controller.source_to_view(src_idx)
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

    def apply_move_view_state(self, cmd: _MoveRowsCmd, *, undo: bool) -> None:
        history = self._context.history_provider()
        if history is None:
            return
        state = history.view_state_for(id(cmd))
        if state is None:
            return
        roots_state = state.get("roots", {})
        if undo:
            self._apply_relative_expansion_mapping(
                cmd.source_paths, self.sort_move_paths(cmd.source_paths), roots_state
            )
            self._restore_selection_paths(state.get("selection_before", []), state.get("current_before"))
            return
        self._apply_relative_expansion_mapping(cmd.source_paths, cmd.placed_paths, roots_state)
        self.restore_selection_at_paths(cmd.placed_paths)

    def on_undo_index_changed(self, new_index: int) -> None:
        tab = self._context.tab
        history = self._context.history_provider()
        if history is None:
            return
        old_index = history.last_undo_index
        if new_index == old_index:
            return

        if new_index > old_index:
            for i in range(old_index, new_index):
                cmd = tab.undo_stack.command(i)
                if isinstance(cmd, _MoveRowsCmd) and history.has_view_state(id(cmd)):
                    self.apply_move_view_state(cmd, undo=False)
        else:
            for i in range(old_index - 1, new_index - 1, -1):
                cmd = tab.undo_stack.command(i)
                if isinstance(cmd, _MoveRowsCmd) and history.has_view_state(id(cmd)):
                    self.apply_move_view_state(cmd, undo=True)
        history.last_undo_index = new_index


__all__ = ["MoveViewState"]
