"""Document mutation gateway facade."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt


class DocumentMutationGateway:
    """Thin forwarding facade for tab mutation helpers."""

    def __init__(self, tab: "JsonTab") -> None:
        self._tab = tab

    def commit_set_data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: Qt.ItemDataRole | int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """Route a delegate ``setData`` call to the matching typed edit command."""
        tab = self._tab
        if tab.editability.is_read_only:
            return False
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        idx = tab.view_controller.proxy_to_source(idx)
        col = idx.column()
        if col == 0:
            return tab.editing.push_rename(idx, value)
        if col == 1:
            return tab.editing.push_change_type(idx, value)
        if col == 2:
            return tab.editing.push_edit_value(idx, value)
        return False

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        return self._tab.editing.push_edit_value(value_index, new_value, label=label)

    def push_insert_rows(self, inserts: list, *, label: str = "insert", target_qname: str | None = None) -> bool:
        return self._tab.editing.push_insert_rows(inserts, label=label, target_qname=target_qname)

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        return self._tab.editing.push_remove_rows(indexes, label=label)

    def push_move_rows_anchor(self, *args, **kwargs) -> bool:
        return self._tab.editing.push_move_rows_anchor(*args, **kwargs)

    def push_move_rows(self, *args, **kwargs) -> bool:
        return self._tab.editing.push_move_rows(*args, **kwargs)

    def push_sort_keys(self, *args, **kwargs) -> bool:
        return self._tab.editing.push_sort_keys(*args, **kwargs)

    def push_switch_field_case(self, *args, **kwargs) -> bool:
        return self._tab.editing.push_switch_field_case(*args, **kwargs)

    def push_edit_value_at(self, row_path: tuple[int, ...], new_value: Any, *, label: str = "edit value") -> bool:
        """Path-based variant of :meth:`push_edit_value`."""
        row_index = self.index_from_path(row_path)
        if not row_index.isValid():
            return False
        model = self._tab.model
        value_index = model.index(row_index.row(), 2, row_index.parent())
        return self._tab.editing.push_edit_value(value_index, new_value, label=label)

    def push_remove_paths(self, paths: list[tuple[int, ...]], *, label: str = "delete") -> bool:
        """Path-based variant of :meth:`push_remove_rows`."""
        indexes = [self.index_from_path(p) for p in paths]
        if not all(i.isValid() for i in indexes):
            return False
        return self._tab.editing.push_remove_rows(indexes, label=label)

    def push_sort_keys_at(self, parent_path: tuple[int, ...], *, recursive: bool = False) -> bool:
        """Path-based variant of :meth:`push_sort_keys`."""
        parent_index = self.index_from_path(parent_path)
        if not parent_index.isValid():
            return False
        return self._tab.editing.push_sort_keys(parent_index, recursive=recursive)

    def begin_macro(self, label: str) -> None:
        undo_stack = self._tab.undo_stack
        if undo_stack is not None:
            undo_stack.beginMacro(label)

    def end_macro(self) -> None:
        undo_stack = self._tab.undo_stack
        if undo_stack is not None:
            undo_stack.endMacro()

    def index_path(self, index: QModelIndex) -> tuple[int, ...]:
        return self._tab.view_controller.index_path(index)

    def index_from_path(self, path: tuple[int, ...]) -> QModelIndex:
        return self._tab.view_controller.index_from_path(path)

    def source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return self._tab.view_controller.source_to_view(source_index)


__all__ = ["DocumentMutationGateway"]
