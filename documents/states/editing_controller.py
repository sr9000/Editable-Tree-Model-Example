"""EditingController -- editing controller for a :class:`documents.tab.JsonTab`.

Plan 21 Phase N: the editing axis is promoted from a passive substate
(``EditingState``, Plan 20 Phase I) to an *active controller* that owns
both the editing data (tree model, mutation gateway, undo history, affix
MRU, last-move-placed cache) **and** the typed-command ``push_*``
behaviour that previously lived as free functions in
``documents/tab_commands.py``.

Subsequent Plan 21 N steps fold the remaining editing helper modules
(``tab_editing.py`` / ``tab_move_view_state.py`` / ``tab_tree_actions.py``)
and the diff/insert primitives onto this controller.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QComboBox

from documents.mutation_gateway import DocumentMutationGateway
from documents.tab_history import TabHistoryController
from documents.tab_number_types import would_drop_fraction_on_type_change
from state.affix_mru import AffixMRU
from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths
from tree.model import JsonTreeModel
from tree.types import JsonType
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_auto, paste_insert_after_zip, paste_replace_zip
from tree_actions.selection import selected_source_rows
from tree_actions.structure import (
    cut_selection,
    delete_selection,
    duplicate_selection,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_out_down,
    move_selection_out_up,
    move_selection_up,
    sort_selection_keys,
)
from undo.commands import (
    _ChangeTypeCmd,
    _EditValueCmd,
    _InsertRowsCmd,
    _MoveRowsCmd,
    _RemoveRowsCmd,
    _RenameCmd,
    _SortKeysCmd,
    _SwitchFieldCaseCmd,
)


class TreeAction(Enum):
    COPY_ONLY = auto()
    CUT = auto()
    PASTE = auto()
    PASTE_ZIP = auto()
    REPLACE_ZIP = auto()
    DELETE = auto()
    DUPLICATE = auto()
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    MOVE_OUT_UP = auto()
    MOVE_OUT_DOWN = auto()
    SORT_KEYS = auto()


# Order matches the historical ``elif`` chain inside ``JsonTab._run_tree_action``.
_ACTIONS: tuple[tuple[TreeAction, Callable[..., bool]], ...] = (
    (TreeAction.COPY_ONLY, copy_selection),
    (TreeAction.CUT, cut_selection),
    (TreeAction.PASTE, paste_auto),
    (TreeAction.PASTE_ZIP, paste_insert_after_zip),
    (TreeAction.REPLACE_ZIP, paste_replace_zip),
    (TreeAction.DELETE, delete_selection),
    (TreeAction.DUPLICATE, duplicate_selection),
    (TreeAction.MOVE_UP, move_selection_up),
    (TreeAction.MOVE_DOWN, move_selection_down),
    (TreeAction.MOVE_OUT_UP, move_selection_out_up),
    (TreeAction.MOVE_OUT_DOWN, move_selection_out_down),
    (TreeAction.SORT_KEYS, lambda view: sort_selection_keys(view, recursive=False)),
)


class EditingController:
    """Per-tab editing controller.

    Owns the tree model, mutation gateway, undo-history controller, affix
    MRU and last-move-placed cache for a single
    :class:`documents.tab.JsonTab`, and implements the typed-command
    ``push_*`` orchestration directly (formerly ``documents.tab_commands``).
    """

    def __init__(self, tab) -> None:
        self._tab = tab
        self.model: JsonTreeModel | None = None
        self.mutations: DocumentMutationGateway | None = None
        self.affix_mru: AffixMRU | None = None
        self.history: TabHistoryController | None = None
        self.last_move_placed: list[tuple[tuple[int, ...], int]] = []

    # ------------------------------------------------------------------
    # Typed-command push helpers (formerly documents/tab_commands.py)
    # ------------------------------------------------------------------

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
        if tab.data_store.is_read_only:
            return False
        if src == dst:
            return False
        parent_item = tab.data_store.model.get_item(parent_index)
        n = parent_item.child_count()
        if not (0 <= src < n and 0 <= dst < n):
            return False
        source_idx = tab.data_store.model.index(src, 0, parent_index)
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
        """Move *sources* to the gap described by ``anchor`` as a single undo command.

        Returns ``False`` when:
        - *sources* is empty,
        - any source would become an ancestor of ``anchor.parent_path``
          (cycle guard), or
        - the move is a no-op (block already lands at the anchor).
        """
        from tree_actions.anchors import anchor_is_cycle, anchor_is_no_op, resolve_anchor_insert_row

        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not sources:
            return False

        model = tab.data_store.model
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
        move_view_state = tab._capture_move_view_state(sources)
        target_qname = tab.view_controller.qualified_name(model.index(sources[0].row(), 0, sources[0].parent()))
        cmd = _MoveRowsCmd(tab, self.make_label(label, target_qname), source_paths, source_names, anchor)
        tab.data_store.undo_stack.push(cmd)
        tab.data_store._move_view_state_by_cmd_id[id(cmd)] = move_view_state
        # Expose placed paths for action-layer post-hooks (esp. macros).
        tab.data_store._last_move_placed = cmd.placed_paths
        tab._apply_move_view_state(cmd, undo=False)
        return True

    def push_move_rows(
        self,
        sources: list,
        target_parent: QModelIndex,
        target_row: int,
        *,
        label: str = "move rows",
    ) -> bool:
        """Legacy pre-Step-9 API. Translates ``(target_parent, target_row)``
        (pre-pop convention) into a ``MoveAnchor`` and delegates."""
        from tree_actions.anchors import pre_pop_target_row_to_anchor

        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not sources:
            return False
        anchor = pre_pop_target_row_to_anchor(tab, target_parent, target_row)
        return self.push_move_rows_anchor(sources, anchor, label=label)

    def push_rename(self, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not name_index.isValid() or name_index.column() != 0:
            return False
        item = tab.data_store.model.get_item(name_index)
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
        cmd = _RenameCmd(
            tab, self.make_label(label, target_qname), tab.view_controller.index_path(name_index), item.name, candidate
        )
        tab.data_store.undo_stack.push(cmd)
        return True

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not value_index.isValid() or value_index.column() != 2:
            return False
        name_idx = tab.data_store.model.index(value_index.row(), 0, value_index.parent())
        item = tab.data_store.model.get_item(name_idx)
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
        cmd = _EditValueCmd(
            tab, self.make_label(label, target_qname), tab.view_controller.index_path(name_idx), old_subtree, applied
        )
        tab.data_store.undo_stack.push(cmd)
        return True

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not type_index.isValid() or type_index.column() != 1:
            return False
        try:
            target_type = new_type if isinstance(new_type, JsonType) else JsonType(str(new_type))
        except ValueError:
            return False
        name_idx = tab.data_store.model.index(type_index.row(), 0, type_index.parent())
        item = tab.data_store.model.get_item(name_idx)
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
        tab.data_store.undo_stack.push(cmd)
        if warn_fraction_loss:
            tab.show_status("Fractional part discarded during float-to-integer conversion", 3000)
        return True

    def push_insert_rows(
        self,
        inserts: list,
        *,
        label: str = "insert",
        target_qname: str | None = None,
    ) -> bool:
        """``inserts`` is a list of ``{parent_path, row, value, name}``."""
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not inserts:
            return False
        qname = (
            target_qname
            if target_qname is not None
            else tab.view_controller.qualified_name(tab.view_controller.index_from_path(inserts[0]["parent_path"]))
        )
        cmd = _InsertRowsCmd(tab, self.make_label(label, qname), inserts)
        tab.data_store.undo_stack.push(cmd)
        return True

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not indexes:
            return False
        ordered = sorted(indexes, key=lambda i: (tab.view_controller.index_path(i.parent()), i.row()), reverse=True)
        removals = []
        for idx in ordered:
            row0 = tab.data_store.model.index(idx.row(), 0, idx.parent())
            item = tab.data_store.model.get_item(row0)
            removals.append(
                {
                    "parent_path": tab.view_controller.index_path(idx.parent()),
                    "row": idx.row(),
                    "name": item.name,
                    "value": item.to_json(),
                }
            )
        target_qname = tab.view_controller.qualified_name(ordered[0])
        cmd = _RemoveRowsCmd(tab, self.make_label(label, target_qname), removals)
        tab.data_store.undo_stack.push(cmd)
        return True

    def push_sort_keys(
        self,
        index: QModelIndex,
        *,
        recursive: bool = False,
        label: str | None = None,
    ) -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not index.isValid():
            return False
        item = tab.data_store.model.get_item(index)
        if item.json_type is not JsonType.OBJECT:
            return False
        old_subtree = item.to_json()
        if not recursive and list(old_subtree.keys()) == sorted(old_subtree.keys()):
            return False
        target_qname = tab.view_controller.qualified_name(index)
        text = label if label is not None else ("sort keys recursive" if recursive else "sort keys")
        cmd = _SortKeysCmd(
            tab, self.make_label(text, target_qname), tab.view_controller.index_path(index), old_subtree, recursive
        )
        tab.data_store.undo_stack.push(cmd)
        return True

    def push_switch_field_case(
        self,
        renames: list[dict[str, Any]],
        *,
        label: str = "switch field case",
        target_qname: str | None = None,
    ) -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if not renames:
            return False

        normalized: list[dict[str, Any]] = []
        by_parent: dict[tuple[int, ...], dict[int, str]] = {}

        for rec in renames:
            path = tuple(rec.get("path", ()))
            old_name = rec.get("old_name")
            new_name = rec.get("new_name")
            if not path or not isinstance(old_name, str) or not isinstance(new_name, str):
                continue
            if old_name == new_name:
                continue
            idx = tab.view_controller.index_from_path(path)
            if not idx.isValid():
                continue
            item = tab.data_store.model.get_item(idx)
            if item.name != old_name:
                continue
            parent = item.parent_item
            if parent is None or parent.json_type is not JsonType.OBJECT:
                continue
            normalized.append({"path": path, "old_name": old_name, "new_name": new_name})
            by_parent.setdefault(path[:-1], {})[path[-1]] = new_name

        if not normalized:
            return False

        # Preflight: reject operations that would create duplicate sibling names.
        for parent_path, updates in by_parent.items():
            parent_index = tab.view_controller.index_from_path(parent_path)
            parent_item = tab.data_store.model.get_item(parent_index)
            final_names: list[str] = []
            for row, child in enumerate(parent_item.child_items):
                if not isinstance(child.name, str):
                    continue
                final_names.append(updates.get(row, child.name))
            if len(set(final_names)) != len(final_names):
                return False

        first_index = tab.view_controller.index_from_path(normalized[0]["path"])
        qname = target_qname if target_qname is not None else tab.view_controller.qualified_name(first_index)
        cmd = _SwitchFieldCaseCmd(tab, self.make_label(label, qname), normalized)
        tab.data_store.undo_stack.push(cmd)
        return True

    # ------------------------------------------------------------------
    # Edit-from-Enter and type-change editor lifecycle (was tab_editing.py)
    # ------------------------------------------------------------------

    def on_type_changed(self, item_index, lossy: bool) -> None:
        tab = self._tab
        # ``change_type`` already emitted ``dataChanged`` for the row, which
        # closes any persistent inline editor that might have been open on the
        # value cell.  We additionally close it explicitly so the row is in a
        # clean state before any auto-reopen below.
        value_index = tab.data_store.model.index(item_index.row(), 2, item_index.parent())
        tab.data_store.view.closePersistentEditor(tab.view_controller.source_to_view(value_index))

        if lossy:
            tab.show_status("Type change dropped existing child nodes", 3000)

        # Auto-reopen the value editor only when the type change came from a
        # user-driven combo commit (Phase 5.1). Programmatic ``model.setData``
        # paths (tests, scripted edits) bypass the delegate entirely so
        # ``_interactive`` stays ``False`` and we avoid the spurious
        # "edit: editing failed" warning that
        # ``tests/test_smoke_mainwindow.py`` regression-tests.
        if not tab.data_store.type_delegate.interactive:
            return
        if not value_index.isValid():
            return
        # Defer via single-shot timer so Qt finishes the current commit cycle
        # (combo close + setModelData unwind) before we open a new editor on the
        # same row.
        pidx = QPersistentModelIndex(value_index)
        QTimer.singleShot(0, lambda: self.reopen_value_editor(pidx))

    def reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        tab = self._tab
        if not value_pindex.isValid():
            return
        value_index = QModelIndex(value_pindex) if isinstance(value_pindex, QPersistentModelIndex) else value_pindex
        if not value_index.isValid():
            return
        flags = tab.data_store.model.flags(value_index)
        if not (flags & Qt.ItemFlag.ItemIsEditable):
            return
        view_index = tab.view_controller.source_to_view(value_index)
        if not view_index.isValid():
            return
        tab.data_store.view.setCurrentIndex(view_index)
        tab.data_store.view.edit(view_index)

    def edit_name_or_value_from_enter(self) -> None:
        """Start editing from Enter with type-column support.

        - Name/Value columns: edit the current editable cell.
        - Type column: open the inline type combobox editor.
        """
        tab = self._tab
        if tab.data_store.view.state() == QAbstractItemView.State.EditingState:
            return
        current = tab.data_store.view.currentIndex()
        if not current.isValid():
            return

        if current.column() == 1:
            if tab.data_store.view.model().flags(current) & Qt.ItemFlag.ItemIsEditable:
                tab.data_store.view.edit(current)
                QTimer.singleShot(0, self.open_active_type_combo_popup)
            return

        candidates: list[QModelIndex] = []
        if current.column() in (0, 2):
            candidates.append(current)
        candidates.extend((current.siblingAtColumn(2), current.siblingAtColumn(0)))

        model = tab.data_store.view.model()
        for idx in candidates:
            if not idx.isValid():
                continue
            if not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable):
                continue
            tab.data_store.view.setCurrentIndex(idx)
            tab.data_store.view.edit(idx)
            return

    def open_active_type_combo_popup(self) -> None:
        tab = self._tab
        for combo in tab.data_store.view.findChildren(QComboBox):
            if combo.parent() is tab.data_store.view.viewport() and combo.isVisible():
                combo.showPopup()
                return

    # ------------------------------------------------------------------
    # Move-row view-state capture/restore (was tab_move_view_state.py)
    # ------------------------------------------------------------------

    def collect_expanded_paths(self) -> list[tuple[int, ...]]:
        """Return paths of every currently expanded row."""
        tab = self._tab
        paths: list[tuple[int, ...]] = []

        def visit(parent_index: QModelIndex) -> None:
            for r in range(tab.data_store.model.rowCount(parent_index)):
                child = tab.data_store.model.index(r, 0, parent_index)
                if not child.isValid():
                    continue
                view_child = tab.view_controller.source_to_view(child)
                if tab.data_store.view.isExpanded(view_child):
                    paths.append(tab.view_controller.index_path(child))
                    visit(child)

        visit(QModelIndex())
        return paths

    def capture_move_view_state(self, sources: list) -> dict[str, Any]:
        tab = self._tab
        roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
        for idx in sources:
            row0 = tab.data_store.model.index(idx.row(), 0, idx.parent())
            if not row0.isValid():
                continue
            key = (tab.view_controller.index_path(row0.parent()), row0.row())
            view_idx = tab.view_controller.source_to_view(row0)
            roots_state[key] = {
                "expanded_root": bool(view_idx.isValid() and tab.data_store.view.isExpanded(view_idx)),
                "expanded_rel": list(iter_expanded_relative_paths(tab.data_store.view, row0)),
            }

        selected_paths = [
            tab.view_controller.index_path(idx) for idx in selected_source_rows(tab.data_store.view) if idx.isValid()
        ]
        current_src = tab.view_controller.proxy_to_source(tab.data_store.view.currentIndex())
        if current_src.isValid():
            current_src = tab.data_store.model.index(current_src.row(), 0, current_src.parent())
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
        tab = self._tab
        ordered_sources = self.sort_move_paths(source_roots)
        for source_root, target_root in zip(ordered_sources, target_roots):
            state = roots_state.get(source_root)
            if state is None:
                continue
            target_parent_path, target_row = target_root
            target_parent = tab.view_controller.index_from_path(target_parent_path)
            target_index = tab.data_store.model.index(target_row, 0, target_parent)
            if not target_index.isValid():
                continue
            target_view = tab.view_controller.source_to_view(target_index)
            if target_view.isValid():
                tab.data_store.view.setExpanded(target_view, bool(state.get("expanded_root", False)))
            apply_expanded_relative_paths(tab.data_store.view, target_index, state.get("expanded_rel", []))

    def _restore_selection_paths(
        self,
        paths: list[tuple[int, ...]],
        current_path: tuple[int, ...] | None,
    ) -> None:
        tab = self._tab
        sm = tab.data_store.view.selectionModel()
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
        """Select the rows at the given ``(parent_path, row)`` tuples after a move."""
        tab = self._tab
        if not placed:
            return
        sm = tab.data_store.view.selectionModel()
        if sm is None:
            return
        selection = QItemSelection()
        first_view_idx = None
        for parent_path, row in placed:
            p = tab.view_controller.index_from_path(parent_path)
            src_idx = tab.data_store.model.index(row, 0, p)
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
        tab = self._tab
        state = tab.data_store._move_view_state_by_cmd_id.get(id(cmd))
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
        tab = self._tab
        old_index = tab.data_store._last_undo_index
        if new_index == old_index:
            return

        if new_index > old_index:
            for i in range(old_index, new_index):
                cmd = tab.data_store.undo_stack.command(i)
                if isinstance(cmd, _MoveRowsCmd) and id(cmd) in tab.data_store._move_view_state_by_cmd_id:
                    self.apply_move_view_state(cmd, undo=False)
        else:
            for i in range(old_index - 1, new_index - 1, -1):
                cmd = tab.data_store.undo_stack.command(i)
                if isinstance(cmd, _MoveRowsCmd) and id(cmd) in tab.data_store._move_view_state_by_cmd_id:
                    self.apply_move_view_state(cmd, undo=True)
        tab.data_store._last_undo_index = new_index

    # ------------------------------------------------------------------
    # Tree-mutation action dispatch (was tab_tree_actions.py)
    # ------------------------------------------------------------------

    def run_tree_action(self, success_message: str, actions: set[TreeAction]) -> None:
        tab = self._tab
        if tab.data_store.is_read_only:
            return
        view = tab.data_store.view
        for tree_action, action in _ACTIONS:
            if tree_action in actions:
                if action(view):
                    tab.show_status(success_message, 1500)
                return

    def do_insert_sibling_before(self) -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        return insert_sibling_before(tab.data_store.view)

    def do_insert_sibling_after(self) -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        return insert_sibling_after(tab.data_store.view)

    def do_insert_child(self) -> bool:
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        return insert_child_current(tab.data_store.view)


__all__ = ["EditingController", "TreeAction"]
