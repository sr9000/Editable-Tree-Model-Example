"""Per-tab editing controller."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PySide6.QtCore import QModelIndex, QObject, QPersistentModelIndex, Qt

from documents.controllers.history import TabHistoryController
from documents.seams.mutation_gateway import DocumentMutationGateway
from documents.states.editing.command_dispatcher import CommandDispatcher
from documents.states.editing.context import EditingContext
from documents.states.editing.inline_edit_controller import InlineEditController
from documents.states.editing.move_view_state import MoveViewState
from documents.states.editing.tree_actions import ACTIONS as _ACTIONS
from documents.states.editing.tree_actions import TreeAction
from state.affix_mru import AffixMRU
from tree.item import JsonTreeItem
from tree.model import JsonTreeModel
from tree_actions.structure import insert_child_current, insert_sibling_after, insert_sibling_before
from undo.commands import _MoveRowsCmd
from undo.diff import DiffApplier


class EditingController(QObject):
    """Own editing state and mutation helpers for one tab."""

    def __init__(self, tab) -> None:
        super().__init__(tab)
        self._tab = tab
        self.model: JsonTreeModel | None = None
        self.mutations: DocumentMutationGateway | None = None
        self.affix_mru: AffixMRU | None = None
        self.history: TabHistoryController | None = None
        self.last_move_placed: list[tuple[tuple[int, ...], int]] = []
        context = EditingContext(tab=tab, move_view_state=None, history_provider=lambda: self.history)
        self._move = MoveViewState(context)
        context = replace(context, move_view_state=self._move)
        self._inline = InlineEditController(context)
        self._commands = CommandDispatcher(context)
        self._diff_applier = DiffApplier(tab)

    # ----- collaborators (use these directly; no more pass-through forwards) -----
    @property
    def commands(self) -> CommandDispatcher:
        """Undo command construction (push_* operations)."""
        return self._commands

    @property
    def inline(self) -> InlineEditController:
        """Inline edit lifecycle (type-change reopen, enter-to-edit, combo popup)."""
        return self._inline

    @property
    def move(self) -> MoveViewState:
        """Move/expand view-state capture & restore."""
        return self._move

    @property
    def diff(self) -> DiffApplier:
        """Surgical model replay used during undo/redo."""
        return self._diff_applier

    # ----- own logic (not pass-throughs) -----
    def run_tree_action(self, success_message: str, actions: set[TreeAction]) -> None:
        tab = self._tab
        if tab.editability.is_read_only:
            return
        view = tab.view_state.view
        for tree_action, action in _ACTIONS:
            if tree_action in actions:
                if action(view):
                    tab.show_status(success_message, 1500)
                return

    def do_insert_sibling_before(self) -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        return insert_sibling_before(tab.view_state.view)

    def do_insert_sibling_after(self) -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        return insert_sibling_after(tab.view_state.view)

    def do_insert_child(self) -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        return insert_child_current(tab.view_state.view)

    def commit_set_data(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        return self._tab.mutations.commit_set_data(index, value, role)


__all__ = ["EditingController", "TreeAction"]
