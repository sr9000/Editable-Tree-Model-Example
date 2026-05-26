"""History seam published on ``JsonTab``.

Phase 0 façade: forwards to fields still owned by ``JsonTab``. Phase 2.2 will
replace this thin object with a full ``TabHistoryController`` that owns the
``QUndoStack`` and view-state map directly.
"""

from __future__ import annotations

from typing import Any

from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths


class TabHistoryFacade:
    """Stable surface for undo/redo and view-state preservation."""

    def __init__(self, tab: Any) -> None:
        self._tab = tab

    @property
    def undo_stack(self):
        return self._tab.undo_stack

    def register_view_state(self, cmd_id: int, state: dict) -> None:
        self._tab._move_view_state_by_cmd_id[cmd_id] = state

    def view_state_for(self, cmd_id: int) -> dict | None:
        return self._tab._move_view_state_by_cmd_id.get(cmd_id)

    def iter_expanded_relative_paths(self, root_index):
        return iter_expanded_relative_paths(self._tab.view, root_index)

    def apply_expanded_relative_paths(self, root_index, paths) -> None:
        apply_expanded_relative_paths(self._tab.view, root_index, paths)


__all__ = ["TabHistoryFacade"]
