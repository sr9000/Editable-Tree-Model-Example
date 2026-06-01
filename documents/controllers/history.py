"""Per-tab undo/history controller."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QUndoStack

from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths


class TabHistoryController(QObject):
    def __init__(self, tab) -> None:
        super().__init__(tab)
        self._tab = tab
        self.undo_stack = QUndoStack(self)
        self._move_view_state_by_cmd_id: dict[int, dict[str, Any]] = {}
        self._last_undo_index: int = self.undo_stack.index()

    def register_view_state(self, cmd_id: int, state: dict) -> None:
        self._move_view_state_by_cmd_id[cmd_id] = state

    def view_state_for(self, cmd_id: int) -> dict | None:
        return self._move_view_state_by_cmd_id.get(cmd_id)

    def has_view_state(self, cmd_id: int) -> bool:
        return cmd_id in self._move_view_state_by_cmd_id

    @property
    def last_undo_index(self) -> int:
        return self._last_undo_index

    @last_undo_index.setter
    def last_undo_index(self, value: int) -> None:
        self._last_undo_index = value

    def iter_expanded_relative_paths(self, root_index):
        return iter_expanded_relative_paths(self._tab.view_state.view, root_index)

    def apply_expanded_relative_paths(self, root_index, paths) -> None:
        apply_expanded_relative_paths(self._tab.view_state.view, root_index, paths)


__all__ = ["TabHistoryController"]
