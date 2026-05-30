"""Per-tab editing controller."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QObject, QPersistentModelIndex, Qt

from documents.states.editing.command_dispatcher import CommandDispatcher
from documents.mutation_gateway import DocumentMutationGateway
from documents.states.editing.inline_edit_controller import InlineEditController
from documents.states.editing.move_view_state import MoveViewState
from documents.tab_history import TabHistoryController
from documents.states.editing.tree_actions import ACTIONS as _ACTIONS
from documents.states.editing.tree_actions import TreeAction
from state.affix_mru import AffixMRU
from tree.item import JsonTreeItem
from tree.model import JsonTreeModel
from tree.types import JsonType
from tree_actions.structure import (
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
)
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
        self._inline = InlineEditController(tab)
        self._move = MoveViewState(tab, lambda: self.history)
        self._commands = CommandDispatcher(tab, move=self._move, history_provider=lambda: self.history)
        self._diff_applier = DiffApplier(tab)

    @staticmethod
    def make_label(text: str, target_qname: str) -> str:
        return CommandDispatcher.make_label(text, target_qname)

    def push_move_row(
        self,
        parent_index: QModelIndex,
        src: int,
        dst: int,
        *,
        label: str = "move row",
    ) -> bool:
        return self._commands.push_move_row(parent_index, src, dst, label=label)

    def push_move_rows_anchor(
        self,
        sources: list,
        anchor: Any,
        *,
        label: str = "move rows",
    ) -> bool:
        return self._commands.push_move_rows_anchor(sources, anchor, label=label)

    def push_move_rows(
        self,
        sources: list,
        target_parent: QModelIndex,
        target_row: int,
        *,
        label: str = "move rows",
    ) -> bool:
        return self._commands.push_move_rows(sources, target_parent, target_row, label=label)

    def push_rename(self, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool:
        return self._commands.push_rename(name_index, new_name, label=label)

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        return self._commands.push_edit_value(value_index, new_value, label=label)

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
        return self._commands.push_change_type(type_index, new_type, label=label)

    def push_insert_rows(
        self,
        inserts: list,
        *,
        label: str = "insert",
        target_qname: str | None = None,
    ) -> bool:
        return self._commands.push_insert_rows(inserts, label=label, target_qname=target_qname)

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        return self._commands.push_remove_rows(indexes, label=label)

    def push_sort_keys(
        self,
        index: QModelIndex,
        *,
        recursive: bool = False,
        label: str | None = None,
    ) -> bool:
        return self._commands.push_sort_keys(index, recursive=recursive, label=label)

    def push_switch_field_case(
        self,
        renames: list[dict[str, Any]],
        *,
        label: str = "switch field case",
        target_qname: str | None = None,
    ) -> bool:
        return self._commands.push_switch_field_case(renames, label=label, target_qname=target_qname)

    def on_type_changed(self, item_index, lossy: bool) -> None:
        self._inline.on_type_changed(item_index, lossy)

    def reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        self._inline.reopen_value_editor(value_pindex)

    def edit_name_or_value_from_enter(self) -> None:
        self._inline.edit_name_or_value_from_enter()

    def open_active_type_combo_popup(self) -> None:
        self._inline.open_active_type_combo_popup()

    def collect_expanded_paths(self) -> list[tuple[int, ...]]:
        return self._move.collect_expanded_paths()

    def capture_move_view_state(self, sources: list) -> dict[str, Any]:
        return self._move.capture_move_view_state(sources)

    def sort_move_paths(self, paths: list[tuple[tuple[int, ...], int]]) -> list[tuple[tuple[int, ...], int]]:
        return self._move.sort_move_paths(paths)

    def restore_selection_at_paths(self, placed: list[tuple[tuple, int]]) -> None:
        self._move.restore_selection_at_paths(placed)

    def apply_move_view_state(self, cmd: _MoveRowsCmd, *, undo: bool) -> None:
        self._move.apply_move_view_state(cmd, undo=undo)

    def on_undo_index_changed(self, new_index: int) -> None:
        self._move.on_undo_index_changed(new_index)

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

    @property
    def diff_applier(self) -> DiffApplier:
        return self._diff_applier

    def diff_apply(self, item: JsonTreeItem, target: Any, item_index: QModelIndex) -> bool:
        return self._diff_applier.apply(item, target, item_index)

    def emit_row_changed(self, item_index: QModelIndex) -> None:
        self._diff_applier.emit_row_changed(item_index)

    def insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        return self._diff_applier.insert_typed_item(parent_item, parent_index, position, value, name=name)

    def commit_set_data(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        return self._tab.mutations.commit_set_data(index, value, role)


__all__ = ["EditingController", "TreeAction"]
