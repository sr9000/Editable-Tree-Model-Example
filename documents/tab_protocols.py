from __future__ import annotations

from typing import Any, Protocol

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt


class JsonTabWidgetMarker:
    """Marker base used by tree_actions to identify tab widgets without importing documents.tab."""


class TabTreeActionsProtocol(Protocol):
    data_store: Any

    def show_status(self, message: str, timeout_ms: int = 3000) -> None: ...


class TabEditingProtocol(Protocol):
    data_store: Any

    def _source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex: ...

    def show_status(self, message: str, timeout_ms: int = 3000) -> None: ...

    def _open_active_type_combo_popup(self) -> None: ...


class TabMoveViewStateProtocol(Protocol):
    data_store: Any

    def _source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex: ...

    def _proxy_to_source(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex: ...

    def _index_path(self, index: QModelIndex) -> tuple[int, ...]: ...

    def _index_from_path(self, path: tuple[int, ...]) -> QModelIndex: ...


class TabCommandsProtocol(Protocol):
    data_store: Any

    def _index_path(self, index: QModelIndex) -> tuple[int, ...]: ...

    def _index_from_path(self, path: tuple[int, ...]) -> QModelIndex: ...

    def _qualified_name(self, index: QModelIndex) -> str: ...

    def _capture_move_view_state(self, sources: list) -> dict[str, Any]: ...

    def _apply_move_view_state(self, cmd: Any, *, undo: bool) -> None: ...

    def show_status(self, message: str, timeout_ms: int = 3000) -> None: ...


class TabValidationViewProtocol(Protocol):
    data_store: Any

    def show_status(self, message: str, timeout_ms: int = 3000) -> None: ...

    def _index_from_path(self, path: tuple[int, ...]) -> QModelIndex: ...

    def _source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex: ...


class TabSetupProtocol(Protocol):
    data_store: Any
    _appearance: Any

    def refresh_actions(self) -> None: ...

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None: ...

    def _on_type_changed(self, item_index: QModelIndex, lossy: bool) -> None: ...

    def _run_tree_action(self, success_message: str, actions: set[Any]) -> None: ...

    def _apply_filter(self) -> None: ...


class TabBootstrapProtocol(TabSetupProtocol, Protocol):
    _navigation: Any
    _editability: Any
    _validation_view: Any
    dirtyChanged: Any
    schemaChanged: Any
    validationChanged: Any

    def edit_name_or_value_from_enter(self) -> None: ...

    def _sync_icon_size_with_font(self) -> None: ...

    def set_monospace_fields_enabled(self, enabled: bool) -> None: ...

    def _severity_provider(self, model_path: tuple[int, ...]) -> str | None: ...

    def _on_validation_changed(self, issue_index: Any) -> None: ...

    def _on_clean_changed(self, clean: bool) -> None: ...

    def _on_undo_index_changed(self, new_index: int) -> None: ...

    def _set_dirty(self, dirty: bool) -> None: ...


class TreeActionsTabProtocol(Protocol):
    data_store: Any

    def show_status(self, message: str, timeout_ms: int = 3000) -> None: ...

    def _qualified_name(self, index: QModelIndex) -> str: ...

    def _restore_selection_at_paths(self, placed: list[tuple[tuple, int]]) -> None: ...

    def edit_name_or_value_from_enter(self) -> None: ...

    def apply_filter(self) -> None: ...


class TabMutationGatewayProtocol(Protocol):
    data_store: Any

    def _proxy_to_source(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex: ...

    def push_rename(self, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool: ...

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool: ...

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool: ...


class TabDataMutationsProtocol(Protocol):
    def commit_set_data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: Qt.ItemDataRole | int = Qt.ItemDataRole.EditRole,
    ) -> bool: ...
