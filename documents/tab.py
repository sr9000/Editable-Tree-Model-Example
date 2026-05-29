from __future__ import annotations

import os
from typing import Any, Callable

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import QWidget

from documents import tab_commands, tab_editing, tab_init, tab_move_view_state, tab_tree_actions
from documents.mutation_gateway import DocumentMutationGateway
from documents.tab_appearance import JsonTabAppearanceController
from documents.tab_data import JsonTabData
from documents.tab_dependencies import JsonTabServices
from documents.tab_editability import JsonTabEditabilityController
from documents.tab_io import save as tab_save
from documents.tab_io import save_as as tab_save_as
from documents.tab_io import snapshot as tab_snapshot
from documents.tab_navigation import JsonTabNavigationController
from documents.tab_paths import index_from_path, index_path, proxy_to_source, qualified_name, source_to_view
from documents.tab_protocols import JsonTabWidgetMarker
from documents.tab_status import on_current_changed, size_hint_for_item
from documents.tab_validation import TabValidationController
from documents.tab_validation_view import JsonTabValidationViewController
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.view import JsonTreeView
from undo.commands import _ChangeTypeCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _EditValueCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _InsertRowsCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _RemoveRowsCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _RenameCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _SortKeysCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _SwitchFieldCaseCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _MoveRowsCmd
from undo.diff import DiffApplier
from validation.index import IssueIndex
from validation.issue import ValidationIssue

_DEFAULT_DATA = tab_init._DEFAULT_DATA

# QUndoCommand.id() values for typed commands that support mergeWith().
# Qt requires id() to fit in a signed 32-bit int (anything larger overflows
# the C++ ``int`` return type and raises ``SystemError`` from PySide).
_CMD_ID_RENAME = 0x0E71_0001
_CMD_ID_EDIT_VALUE = 0x0E71_0002

# Time window in seconds during which two consecutive same-path edits
# collapse into one undo entry. Tuned for keystroke-level typing.
_MERGE_WINDOW_SECONDS = 0.5


class JsonTab(QWidget, JsonTabWidgetMarker):
    _appearance: JsonTabAppearanceController | None = None
    _navigation: JsonTabNavigationController | None = None
    _editability: JsonTabEditabilityController | None = None
    _validation_view: JsonTabValidationViewController | None = None

    dirtyChanged = Signal(bool)
    schemaChanged = Signal(object)
    validationChanged = Signal(object)

    data_store: JsonTabData = None  # populated by tab_init.bootstrap
    _diff_applier: DiffApplier = None

    def eventFilter(self, watched, event):  # type: ignore[override]
        navigation = self._navigation
        if navigation is not None and navigation.handle_event_filter(watched, event):
            return True
        return super().eventFilter(watched, event)

    def __init__(
        self,
        update_actions_callback: Callable[[], None] | None = None,
        status_message_callback: Callable[[str, int], None] | None = None,
        data: Any = _DEFAULT_DATA,
        file_path: str | None = None,
        show_root: bool = False,
        parent=None,
        permanent_message_callback: Callable[[str], None] | None = None,
        theme: ThemeSpec | None = None,
        icon_provider: IconProvider | None = None,
        save_format: str | None = None,
        *,
        services: JsonTabServices | None = None,
    ):
        super().__init__(parent)

        self._diff_applier = DiffApplier(self)

        tab_init.bootstrap(
            self,
            update_actions_callback=update_actions_callback,
            status_message_callback=status_message_callback,
            permanent_message_callback=permanent_message_callback,
            data=data,
            file_path=file_path,
            show_root=show_root,
            theme=theme,
            icon_provider=icon_provider,
            save_format=save_format,
            services=services,
        )

    def set_read_only(self, enabled: bool) -> None:
        editability = self._editability
        if editability is not None:
            editability.set_read_only(enabled)

    @property
    def is_read_only(self) -> bool:
        return self.data_store.is_read_only

    @property
    def mutations(self) -> DocumentMutationGateway:
        """Typed accessor for the document mutation gateway.

        Replaces ``tab.data_store.mutations`` for external callers; see
        ``plans/20-decouple-jsontab.md`` Phase B.
        """
        return self.data_store.mutations

    # -- Phase C: typed file-state accessors ---------------------
    # Forward to JsonTabDataFacade so external callers (app/, undo/,
    # tree_actions/, state/) stop reaching into tab.data_store.
    @property
    def file_path(self) -> str | None:
        return self.data_store.file_path

    @file_path.setter
    def file_path(self, value: str | None) -> None:
        self.data_store.file_path = value

    @property
    def save_format(self) -> str | None:
        return self.data_store.save_format

    @save_format.setter
    def save_format(self, value: str | None) -> None:
        self.data_store.save_format = value

    @property
    def is_dirty(self) -> bool:
        return self.data_store.is_dirty

    @property
    def schema_source(self):
        return self.data_store.schema_source

    @property
    def schema_ref(self):
        return self.data_store.schema_ref

    @property
    def validation(self) -> TabValidationController:
        return self.data_store.validation

    @property
    def undo_stack(self):
        return self.data_store.undo_stack

    @property
    def view(self) -> JsonTreeView:
        """Typed accessor for the underlying tree view.

        Replaces ``tab.data_store.view`` for external callers; see
        ``plans/20-decouple-jsontab.md`` Phase D.
        """
        return self.data_store.view

    def closeEvent(self, event):  # type: ignore[override]
        self.data_store.validation.release()
        super().closeEvent(event)

    def goto_validation_issue(self, issue: ValidationIssue, *, edit: bool = False) -> bool:
        validation_view = self._validation_view
        return validation_view is not None and validation_view.goto_validation_issue(issue, edit=edit)

    def _severity_provider(self, model_path: tuple[int, ...]) -> str | None:
        """Lazily queried by the model for VALIDATION_SEVERITY_ROLE."""
        validation_view = self._validation_view
        return validation_view.severity_provider(model_path) if validation_view is not None else None

    def _on_validation_changed(self, _index: IssueIndex) -> None:
        validation_view = self._validation_view
        if validation_view is not None:
            validation_view.on_validation_changed(_index)

    def set_theme(self, theme: ThemeSpec, icon_provider: IconProvider | None = None) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.set_theme(theme, icon_provider)

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.set_monospace_fields_enabled(enabled)

    def set_regular_font_family(self, family: str) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.set_regular_font_family(family)

    def set_monospace_font_family(self, family: str) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.set_monospace_font_family(family)

    def set_editor_font_point_size(self, point_size: int) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.set_editor_font_point_size(point_size)

    def apply_font_profile(self, profile) -> None:
        """Aspect entry point called by ``FontController``.

        Order matters: family must be set before point size so the column
        scaler sees the final font width, and the monospace toggle must
        come last because it triggers a viewport repaint that picks up
        the freshly-installed delegate fonts.
        """
        appearance = self._appearance
        if appearance is not None:
            appearance.apply_font_profile(profile)

    @staticmethod
    def _proxy_to_source(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return proxy_to_source(index)

    def _source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return source_to_view(self, source_index)

    def _apply_filter(self) -> None:
        self.data_store.proxy.set_filter_text(self.data_store.search_edit.text())

    # ── Public typed accessors (Stage 01 of getattr-elimination plan) ──────

    def apply_filter(self) -> None:
        """Re-apply the search filter to the proxy model."""
        self._apply_filter()

    def refresh_actions(self) -> None:
        self.data_store._host.refresh_actions()

    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Publish *message* via the injected host."""
        self.data_store._host.show_status_message(message, timeout_ms)

    def show_permanent_message(self, message: str) -> None:
        self.data_store._host.show_permanent_message(message)

    def _on_model_reset(self) -> None:
        # Force-resize so a brand-new model always gets snug initial widths,
        # regardless of whether the user had previously hand-resized those cols.
        self.resize_key_columns(force=True)

    def resize_key_columns(self, force: bool = False) -> None:
        """Snap name/type columns to content width.

        When *force* is False (the default), columns that the user has
        manually resized (tracked in ``_user_sized_columns``) are left alone.
        Pass ``force=True`` (e.g. on model reset) to override.
        """
        appearance = self._appearance
        if appearance is not None:
            appearance.resize_key_columns(force=force)

    def _scale_columns_for_font(self, old_pt: int, new_pt: int) -> None:
        """Proportionally scale name/type column widths when the font changes.

        Columns the user has hand-resized are left alone.  The value column
        (col 2) is never touched because it is set to stretch.
        """
        appearance = self._appearance
        if appearance is not None:
            appearance.scale_columns_for_font(old_pt, new_pt)

    def _set_font_pt(self, pt: int) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.set_font_pt(pt)

    def _sync_icon_size_with_font(self) -> None:
        # Keep type-column icons visually in step with the active tree font.
        appearance = self._appearance
        if appearance is not None:
            appearance.sync_icon_size_with_font()

    def zoom_in(self) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.zoom_in()

    def zoom_out(self) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.zoom_out()

    def zoom_reset(self) -> None:
        appearance = self._appearance
        if appearance is not None:
            appearance.zoom_reset()

    def _on_type_changed(self, item_index, lossy: bool) -> None:
        tab_editing.on_type_changed(self, item_index, lossy)

    def _reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        tab_editing.reopen_value_editor(self, value_pindex)

    def edit_name_or_value_from_enter(self) -> None:
        tab_editing.edit_name_or_value_from_enter(self)

    def _open_active_type_combo_popup(self) -> None:
        tab_editing.open_active_type_combo_popup(self)

    def _set_dirty(self, dirty: bool) -> None:
        self.data_store.io.set_dirty(dirty)

    def _on_clean_changed(self, clean: bool) -> None:
        self.data_store.io.on_clean_changed(clean)

    def display_name(self) -> str:
        if self.data_store.file_path:
            # ``os.path.basename`` is platform-aware on POSIX (only "/") so we
            # also strip "\\" explicitly to handle Windows-style paths produced
            # by ``QFileDialog`` and similar APIs regardless of host OS.
            name = os.path.basename(self.data_store.file_path.replace("\\", "/")) or "Untitled"
        else:
            name = "Untitled"
        return f"{name} *" if self.data_store.is_dirty else name

    def save(self) -> bool:
        return tab_save(self)

    def save_as(self, path: str | None = None) -> bool:
        return tab_save_as(self, path=path)

    def _snapshot(self) -> Any:
        return tab_snapshot(self)

    def _index_path(self, index: QModelIndex) -> tuple[int, ...]:
        return index_path(self, index)

    def _index_from_path(self, path: tuple[int, ...]) -> QModelIndex:
        return index_from_path(self, path)

    def _qualified_name(self, index: QModelIndex) -> str:
        return qualified_name(self, index)

    def _size_hint_for_item(self, item: JsonTreeItem) -> str | None:
        return size_hint_for_item(item)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        on_current_changed(self, current, _previous)

    def _collect_expanded_paths(self) -> list[tuple[int, ...]]:
        return tab_move_view_state.collect_expanded_paths(self)

    def _capture_move_view_state(self, sources: list) -> dict[str, Any]:
        return tab_move_view_state.capture_move_view_state(self, sources)

    def _apply_move_view_state(self, cmd: _MoveRowsCmd, *, undo: bool) -> None:
        tab_move_view_state.apply_move_view_state(self, cmd, undo=undo)

    def _on_undo_index_changed(self, new_index: int) -> None:
        tab_move_view_state.on_undo_index_changed(self, new_index)

    # ------------------------------------------------------------------
    # Smart-restore diff helpers
    # ------------------------------------------------------------------

    def _diff_apply(self, item: JsonTreeItem, target: Any, item_index: QModelIndex) -> bool:
        return self._diff_applier.apply(item, target, item_index)

    # -- low-level mutators used by diff and typed commands --------------

    def _emit_row_changed(self, item_index: QModelIndex) -> None:
        self._diff_applier.emit_row_changed(item_index)

    def _insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        return self._diff_applier.insert_typed_item(parent_item, parent_index, position, value, name=name)

    def commit_set_data(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        return self.data_store.mutations.commit_set_data(index, value, role)

    # ------------------------------------------------------------------
    # Typed-command public API (action/compensation, no full-tree snapshot)
    # ------------------------------------------------------------------

    def push_move_row(self, parent_index: QModelIndex, src: int, dst: int, *, label: str = "move row") -> bool:
        return tab_commands.push_move_row(self, parent_index, src, dst, label=label)

    def push_move_rows_anchor(
        self,
        sources: list,
        anchor: "MoveAnchor",  # noqa: F821 — see tab_commands
        *,
        label: str = "move rows",
    ) -> bool:
        return tab_commands.push_move_rows_anchor(self, sources, anchor, label=label)

    def push_move_rows(
        self,
        sources: list,
        target_parent: QModelIndex,
        target_row: int,
        *,
        label: str = "move rows",
    ) -> bool:
        return tab_commands.push_move_rows(self, sources, target_parent, target_row, label=label)

    def _restore_selection_at_paths(self, placed: list[tuple[tuple, int]]) -> None:
        tab_move_view_state.restore_selection_at_paths(self, placed)

    def push_rename(self, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool:
        return tab_commands.push_rename(self, name_index, new_name, label=label)

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        return tab_commands.push_edit_value(self, value_index, new_value, label=label)

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
        return tab_commands.push_change_type(self, type_index, new_type, label=label)

    def push_insert_rows(self, inserts: list, *, label: str = "insert", target_qname: str | None = None) -> bool:
        return tab_commands.push_insert_rows(self, inserts, label=label, target_qname=target_qname)

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        return tab_commands.push_remove_rows(self, indexes, label=label)

    def push_sort_keys(self, index: QModelIndex, *, recursive: bool = False, label: str | None = None) -> bool:
        return tab_commands.push_sort_keys(self, index, recursive=recursive, label=label)

    def push_switch_field_case(
        self,
        renames: list[dict[str, Any]],
        *,
        label: str = "switch field case",
        target_qname: str | None = None,
    ) -> bool:
        return tab_commands.push_switch_field_case(self, renames, label=label, target_qname=target_qname)

    def _run_tree_action(
        self,
        success_message: str,
        actions: set[tab_tree_actions.TreeAction],
    ) -> None:
        tab_tree_actions.run_tree_action(self, success_message, actions)

    def insert_sibling_before(self) -> bool:
        return tab_tree_actions.do_insert_sibling_before(self)

    def insert_sibling_after(self) -> bool:
        return tab_tree_actions.do_insert_sibling_after(self)

    def insert_child(self) -> bool:
        return tab_tree_actions.do_insert_child(self)
