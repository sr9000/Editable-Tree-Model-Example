"""Document mutation gateway façade.

This module publishes a *stable seam* on top of the current ``JsonTab`` API.
External callers (``tree_actions``, ``undo``, ``app``) should go through
``tab.data_store.mutations.*`` so that the underlying implementation can move out of
``JsonTab`` in a later commit without churning every call site.

For Phase 0 every method here simply delegates back to the existing
``JsonTab`` implementation. The class deliberately does **not** import
``JsonTab`` to keep the dependency direction clean — the gateway is held as
an attribute by the tab and uses duck typing against the tab instance it
receives at construction time.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt


class DocumentMutationGateway:
    """Thin forwarding façade for document mutations.

    Phase 0 implementation: every method calls back into the tab. Phase 2.4
    will replace these forwards with a real implementation that depends only
    on the model, view, and history controller.
    """

    def __init__(self, tab: Any) -> None:
        self._tab = tab

    # ----- value mutation -------------------------------------------------
    def commit_set_data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: Qt.ItemDataRole | int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Route a single ``setData`` from a delegate to the right typed undo
        command (rename / change-type / edit-value).

        Phase-2.4: the routing body lives here instead of on ``JsonTab``; the
        tab method becomes a one-line delegation.
        """
        tab = self._tab
        if tab.data_store.is_read_only:
            return False
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        idx = tab._proxy_to_source(idx)
        col = idx.column()
        if col == 0:
            return tab.push_rename(idx, value)
        if col == 1:
            return tab.push_change_type(idx, value)
        if col == 2:
            return tab.push_edit_value(idx, value)
        return False

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        return self._tab.push_edit_value(value_index, new_value, label=label)

    # ----- structural mutation -------------------------------------------
    def push_insert_rows(self, inserts: list, *, label: str = "insert", target_qname: str | None = None) -> bool:
        return self._tab.push_insert_rows(inserts, label=label, target_qname=target_qname)

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        return self._tab.push_remove_rows(indexes, label=label)

    def push_move_rows_anchor(self, *args, **kwargs) -> bool:
        return self._tab.push_move_rows_anchor(*args, **kwargs)

    def push_move_rows(self, *args, **kwargs) -> bool:
        return self._tab.push_move_rows(*args, **kwargs)

    def push_sort_keys(self, *args, **kwargs) -> bool:
        return self._tab.push_sort_keys(*args, **kwargs)

    def push_switch_field_case(self, *args, **kwargs) -> bool:
        return self._tab.push_switch_field_case(*args, **kwargs)

    # ----- macro framing --------------------------------------------------
    def begin_macro(self, label: str) -> None:
        self._tab.data_store.undo_stack.beginMacro(label)

    def end_macro(self) -> None:
        self._tab.data_store.undo_stack.endMacro()

    # ----- path / view helpers (read-only) -------------------------------
    def index_path(self, index: QModelIndex) -> tuple[int, ...]:
        return self._tab._index_path(index)

    def index_from_path(self, path: tuple[int, ...]) -> QModelIndex:
        return self._tab._index_from_path(path)

    def source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return self._tab._source_to_view(source_index)


__all__ = ["DocumentMutationGateway"]
