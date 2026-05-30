"""Undo-command construction helpers for editing operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import QModelIndex

from documents.tab_number_types import would_drop_fraction_on_type_change
from tree.types import JsonType
from tree_actions.anchors import anchor_is_cycle, anchor_is_no_op, pre_pop_target_row_to_anchor, resolve_anchor_insert_row
from undo.commands import _ChangeTypeCmd, _EditValueCmd, _MoveRowsCmd, _RenameCmd


class CommandDispatcher:
    def __init__(self, tab, *, move, history_provider: Callable[[], Any | None]) -> None:
        self._tab = tab
        self._move = move
        self._history_provider = history_provider

    @staticmethod
    def make_label(text: str, target_qname: str) -> str:
        timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
        return f"[{timestamp}] {text} @ {target_qname}"

    def push_move_row(
        self,
        parent_index: QModelIndex,
        src: int,
        dst: int,
        *,
        label: str = "move row",
    ) -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if src == dst:
            return False
        parent_item = tab.model.get_item(parent_index)
        n = parent_item.child_count()
        if not (0 <= src < n and 0 <= dst < n):
            return False
        source_idx = tab.model.index(src, 0, parent_index)
        # push_move_rows uses pre-pop target_row; dst is post-pop.
        # Forward move (src < dst): removing src shifts later rows down by 1,
        # so pre-pop target = dst + 1 to land at the same final position.
        # Backward move (src > dst): no shift needed, pre-pop target = dst.
        pre_pop_target = dst + 1 if src < dst else dst
        return self.push_move_rows([source_idx], parent_index, pre_pop_target, label=label)

    def push_move_rows_anchor(
        self,
        sources: list,
        anchor: Any,
        *,
        label: str = "move rows",
    ) -> bool:
        """Move ``sources`` to the gap described by ``anchor`` as one undo command."""
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if not sources:
            return False

        model = tab.model
        # Snapshot every source's (parent_path, row) BEFORE any mutation.
        source_paths: list[tuple[tuple, int]] = []
        source_names: list[Any] = []
        for idx in sources:
            row0 = model.index(idx.row(), 0, idx.parent())
            source_paths.append((tab.view_controller.index_path(row0.parent()), row0.row()))
            source_names.append(model.get_item(row0).name)

        # Cycle guard.
        if anchor_is_cycle(anchor, source_paths):
            tab.show_status("Cannot move a parent into its own descendant", 3000)
            return False

        # No-op guard (path-only). For at_end, resolve to a concrete row first
        # and compare against the would-be insert position.
        if anchor_is_no_op(anchor, source_paths):
            return False
        if anchor.is_at_end:
            resolve_anchor_insert_row(model, tab, anchor, source_paths)
            same_parent_sources = sorted(r for p, r in source_paths if p == anchor.parent_path)
            if same_parent_sources:
                parent_index = tab.view_controller.index_from_path(anchor.parent_path)
                parent_count = model.rowCount(parent_index)
                last_src = same_parent_sources[-1]
                is_contiguous = all(b - a == 1 for a, b in zip(same_parent_sources, same_parent_sources[1:]))
                # If the block is contiguous and already sits as the suffix, at_end is a no-op.
                if is_contiguous and last_src == parent_count - 1 and len(same_parent_sources) == len(source_paths):
                    return False

        # Build the command.
        move_view_state = self._move.capture_move_view_state(sources)
        target_qname = tab.view_controller.qualified_name(model.index(sources[0].row(), 0, sources[0].parent()))
        cmd = _MoveRowsCmd(tab, self.make_label(label, target_qname), source_paths, source_names, anchor)
        tab.undo_stack.push(cmd)
        history = self._history_provider()
        if history is not None:
            history.register_view_state(id(cmd), move_view_state)
        # Expose placed paths for action-layer post-hooks (esp. macros).
        tab.editing.last_move_placed = cmd.placed_paths
        self._move.apply_move_view_state(cmd, undo=False)
        return True

    def push_move_rows(
        self,
        sources: list,
        target_parent: QModelIndex,
        target_row: int,
        *,
        label: str = "move rows",
    ) -> bool:
        """Translate the legacy pre-pop target into a ``MoveAnchor`` and delegate."""
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if not sources:
            return False
        anchor = pre_pop_target_row_to_anchor(tab, target_parent, target_row)
        return self.push_move_rows_anchor(sources, anchor, label=label)

    def push_rename(self, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if not name_index.isValid() or name_index.column() != 0:
            return False
        item = tab.model.get_item(name_index)
        if not isinstance(new_name, str):
            return False
        candidate = new_name.strip()
        if not candidate or candidate == item.name:
            return False
        if item.parent_item is None or item.parent_item.json_type is JsonType.ARRAY:
            return False
        if item.parent_item.json_type is JsonType.OBJECT:
            siblings = {c.name for c in item.parent_item.child_items if c is not item and isinstance(c.name, str)}
            if candidate in siblings:
                return False
        target_qname = tab.view_controller.qualified_name(name_index)
        cmd = _RenameCmd(tab, self.make_label(label, target_qname), tab.view_controller.index_path(name_index), item.name, candidate)
        tab.undo_stack.push(cmd)
        return True

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if not value_index.isValid() or value_index.column() != 2:
            return False
        name_idx = tab.model.index(value_index.row(), 0, value_index.parent())
        item = tab.model.get_item(name_idx)
        old_subtree = item.to_json()
        # Honour explicit_type strict coercion when the type was pinned.
        if item.explicit_type and item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
            ok, coerced = item._coerce_value_for_type(item.json_type, new_value, strict=True)
            if not ok:
                return False
            applied = coerced
        else:
            applied = new_value
        # No-op detection on the affected subtree (subset comparison).
        if old_subtree == applied and isinstance(applied, type(old_subtree)):
            return False
        target_qname = tab.view_controller.qualified_name(name_idx)
        cmd = _EditValueCmd(tab, self.make_label(label, target_qname), tab.view_controller.index_path(name_idx), old_subtree, applied)
        tab.undo_stack.push(cmd)
        return True

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if not type_index.isValid() or type_index.column() != 1:
            return False
        try:
            target_type = new_type if isinstance(new_type, JsonType) else JsonType(str(new_type))
        except ValueError:
            return False
        name_idx = tab.model.index(type_index.row(), 0, type_index.parent())
        item = tab.model.get_item(name_idx)
        if item.json_type is target_type:
            return False
        warn_fraction_loss = would_drop_fraction_on_type_change(item, target_type)
        old_subtree = item.to_json()
        old_explicit = item.explicit_type
        old_type = item.json_type
        target_qname = tab.view_controller.qualified_name(name_idx)
        cmd = _ChangeTypeCmd(
            tab,
            self.make_label(label, target_qname),
            tab.view_controller.index_path(name_idx),
            old_subtree,
            old_explicit,
            old_type,
            target_type,
        )
        tab.undo_stack.push(cmd)
        if warn_fraction_loss:
            tab.show_status("Fractional part discarded during float-to-integer conversion", 3000)
        return True


__all__ = ["CommandDispatcher"]
