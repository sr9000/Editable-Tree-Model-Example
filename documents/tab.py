from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPersistentModelIndex, Qt, QTimer, Signal
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QWidget

from documents import tab_commands
from documents.mutation_gateway import DocumentMutationGateway
from documents.tab_appearance import JsonTabAppearanceController
from documents.tab_data import JsonTabData
from documents.tab_demo_data import build_demo_data
from documents.tab_dependencies import JsonTabServices, build_legacy_json_tab_services
from documents.tab_editability import JsonTabEditabilityController
from documents.tab_io import save as tab_save
from documents.tab_io import save_as as tab_save_as
from documents.tab_io import snapshot as tab_snapshot
from documents.tab_navigation import JsonTabNavigationController
from documents.tab_paths import index_from_path, index_path, proxy_to_source, qualified_name, source_to_view
from documents.tab_setup import (
    init_delegates_and_connections,
    init_layout,
    init_model,
    init_search_filter,
    init_shortcuts,
    init_validation_state,
)
from documents.tab_status import on_current_changed, size_hint_for_item
from documents.tab_validation_view import JsonTabValidationViewController
from state.affix_mru import AffixMRU
from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
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
from undo.diff import DiffApplier
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.schema_registry import SchemaSource
from validation.schema_source import SchemaRef


_DEFAULT_DATA = object()

# QUndoCommand.id() values for typed commands that support mergeWith().
# Qt requires id() to fit in a signed 32-bit int (anything larger overflows
# the C++ ``int`` return type and raises ``SystemError`` from PySide).
_CMD_ID_RENAME = 0x0E71_0001
_CMD_ID_EDIT_VALUE = 0x0E71_0002

# Time window in seconds during which two consecutive same-path edits
# collapse into one undo entry. Tuned for keystroke-level typing.
_MERGE_WINDOW_SECONDS = 0.5



class JsonTab(QWidget):
    _appearance: JsonTabAppearanceController | None = None
    _navigation: JsonTabNavigationController | None = None
    _editability: JsonTabEditabilityController | None = None
    _validation_view: JsonTabValidationViewController | None = None

    dirtyChanged = Signal(bool)
    schemaChanged = Signal(object)
    validationChanged = Signal(object)

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
        self.data_store = JsonTabData()
        self._appearance = JsonTabAppearanceController(self.data_store)
        self.data_store.appearance = self._appearance
        self._navigation = JsonTabNavigationController(self.data_store, self.edit_name_or_value_from_enter)
        self._editability = JsonTabEditabilityController(self.data_store)
        self.data_store.editability = self._editability
        self._validation_view = JsonTabValidationViewController(self)

        # All parts stored inside self.data_store are populated here:
        resolved_services = services or build_legacy_json_tab_services(
            update_actions_callback=update_actions_callback,
            status_message_callback=status_message_callback,
            permanent_message_callback=permanent_message_callback,
            theme=theme,
            icon_provider=icon_provider,
        )
        if services is not None and (theme is not None or icon_provider is not None):
            resolved_services = JsonTabServices(
                host=services.host,
                theme=theme if theme is not None else services.theme,
                icon_provider=icon_provider if icon_provider is not None else services.icon_provider,
            )

        self.data_store._host = resolved_services.host
        self._appearance.initialize(resolved_services.theme, resolved_services.icon_provider)

        init_layout(self)
        self._editability.capture_editable_view_state()
        self._sync_icon_size_with_font()

        # option to edit headers is not needed
        # self.header_editor = HeaderViewEditorMixin(self.data_store.view.header())

        if data is _DEFAULT_DATA:
            model_data = build_demo_data()
        else:
            model_data = data if data is not None else {}

        self.data_store.affix_mru = AffixMRU()

        # Phase-2.3: file path / save format / dirty flag move to a
        # QObject controller owned by the tab.
        from documents.tab_io_controller import TabIOController

        self.data_store.io = TabIOController(self, file_path=file_path, save_format=save_format)
        self.data_store.io.dirtyChanged.connect(self.dirtyChanged.emit)

        init_model(self, model_data, show_root=show_root)
        # Phase-2.2: undo stack and view-state map move to a dedicated
        # QObject controller owned by the tab.
        from documents.tab_history import TabHistoryController

        self.data_store.history = TabHistoryController(self)
        self.data_store.affix_mru.bootstrap_from_tree(self.data_store.model.root_item)
        # Phase-0 façade: publishes a stable mutation seam over the current
        # in-tab implementation; later commits move the implementation out.
        self.data_store.mutations = DocumentMutationGateway(self)

        # Phase-2.1: schema / validation / debounce timer / registry binding
        # are owned by an explicit QObject controller parented to the tab.
        from documents.tab_validation import TabValidationController

        self.data_store.validation = TabValidationController(
            self,
            self.data_store.model,
            on_schema_changed=lambda ref: self.schemaChanged.emit(ref),
            on_validation_changed=lambda idx: self.validationChanged.emit(idx),
            initial_data=model_data,
        )

        init_delegates_and_connections(self)
        self.set_monospace_fields_enabled(self.data_store._monospace_fields_enabled)
        init_shortcuts(self)
        init_search_filter(self)
        # Plug the severity provider before init_validation_state so the first
        # revalidate() → dataChanged repaint already has the provider ready.
        self.data_store.model.set_issue_index_provider(self._severity_provider)
        self.validationChanged.connect(self._on_validation_changed)
        init_validation_state(self, model_data)
        self.data_store._diff_applier = DiffApplier(self)

        self.data_store.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.data_store.undo_stack.indexChanged.connect(self._on_undo_index_changed)
        self.data_store.undo_stack.setClean()
        self._set_dirty(False)

    def set_read_only(self, enabled: bool) -> None:
        editability = self._editability
        if editability is not None:
            editability.set_read_only(enabled)

    def set_schema_view_source(self, source: SchemaSource | None) -> None:
        self.data_store.validation.set_schema_view_source(source)

    def _init_validation_state(self, model_data: Any, *, doc_path: Path | None = None) -> None:
        self.data_store.validation.init_state(model_data, doc_path=doc_path)

    def set_schema(self, ref: SchemaRef) -> None:
        self.data_store.validation.set_schema(ref)

    def set_schema_from_source(self, source: SchemaSource) -> None:
        self.data_store.validation.set_schema_from_source(source)

    def clear_schema(self) -> None:
        self.data_store.validation.clear_schema()

    def closeEvent(self, event):  # type: ignore[override]
        self.data_store.validation.release()
        super().closeEvent(event)

    def revalidate(self) -> None:
        self.data_store.validation.revalidate()

    # ── auto-rescan API ───────────────────────────────────────────────────

    def set_auto_rescan(self, enabled: bool) -> None:
        """Enable or disable automatic revalidation on model mutations.

        When *enabled*, any ``dataChanged``, ``rowsInserted``, ``rowsRemoved``,
        ``rowsMoved``, or ``modelReset`` signal from the tree model arms a
        250 ms trailing debounce timer that calls ``revalidate()``.
        Disabling cancels any pending debounce.
        """
        self.data_store.validation.set_auto_rescan(enabled)

    # ─────────────────────────────────────────────────────────────────────

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
        # ``change_type`` already emitted ``dataChanged`` for the row, which
        # closes any persistent inline editor that might have been open on
        # the value cell. We additionally close it explicitly so the row is
        # in a clean state before any auto-reopen below.
        value_index = self.data_store.model.index(item_index.row(), 2, item_index.parent())
        self.data_store.view.closePersistentEditor(self._source_to_view(value_index))

        if lossy:
            self.show_status("Type change dropped existing child nodes", 3000)

        # Auto-reopen the value editor only when the type change came from
        # a user-driven combo commit (Phase 5.1). Programmatic
        # ``model.setData`` paths (tests, scripted edits) bypass the
        # delegate entirely so ``_interactive`` stays ``False`` and we
        # avoid the spurious "edit: editing failed" warning that
        # ``tests/test_smoke_mainwindow.py`` regression-tests.
        if not self.data_store.type_delegate.interactive:
            return
        if not value_index.isValid():
            return
        # Defer via single-shot timer so Qt finishes the current commit
        # cycle (combo close + setModelData unwind) before we open a new
        # editor on the same row.
        pidx = QPersistentModelIndex(value_index)
        QTimer.singleShot(0, lambda: self._reopen_value_editor(pidx))

    def _reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        if not value_pindex.isValid():
            return
        value_index = QModelIndex(value_pindex) if isinstance(value_pindex, QPersistentModelIndex) else value_pindex
        if not value_index.isValid():
            return
        flags = self.data_store.model.flags(value_index)
        if not (flags & Qt.ItemFlag.ItemIsEditable):
            return
        view_index = self._source_to_view(value_index)
        if not view_index.isValid():
            return
        self.data_store.view.setCurrentIndex(view_index)
        self.data_store.view.edit(view_index)

    def edit_name_or_value_from_enter(self) -> None:
        """Start editing from Enter with type-column support.

        - Name/Value columns: edit the current editable cell.
        - Type column: open the inline type combobox editor.
        """
        if self.data_store.view.state() == QAbstractItemView.State.EditingState:
            return
        current = self.data_store.view.currentIndex()
        if not current.isValid():
            return

        if current.column() == 1:
            if self.data_store.view.model().flags(current) & Qt.ItemFlag.ItemIsEditable:
                self.data_store.view.edit(current)
                QTimer.singleShot(0, self._open_active_type_combo_popup)
            return

        candidates: list[QModelIndex] = []
        if current.column() in (0, 2):
            candidates.append(current)
        candidates.extend((current.siblingAtColumn(2), current.siblingAtColumn(0)))

        model = self.data_store.view.model()
        for idx in candidates:
            if not idx.isValid():
                continue
            if not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable):
                continue
            self.data_store.view.setCurrentIndex(idx)
            self.data_store.view.edit(idx)
            return

    def _open_active_type_combo_popup(self) -> None:
        for combo in self.data_store.view.findChildren(QComboBox):
            if combo.parent() is self.data_store.view.viewport() and combo.isVisible():
                combo.showPopup()
                return

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
        """Return paths of every currently expanded row.

        Kept as a standalone helper because a few tests (and any future
        view-state save/restore) want to enumerate expansion. It is no
        longer part of any undo/redo path.
        """
        paths: list[tuple[int, ...]] = []

        def visit(parent_index: QModelIndex) -> None:
            for r in range(self.data_store.model.rowCount(parent_index)):
                child = self.data_store.model.index(r, 0, parent_index)
                if not child.isValid():
                    continue
                view_child = self._source_to_view(child)
                if self.data_store.view.isExpanded(view_child):
                    paths.append(self._index_path(child))
                    visit(child)

        visit(QModelIndex())
        return paths

    def _capture_move_view_state(self, sources: list) -> dict[str, Any]:
        roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]] = {}
        for idx in sources:
            row0 = self.data_store.model.index(idx.row(), 0, idx.parent())
            if not row0.isValid():
                continue
            key = (self._index_path(row0.parent()), row0.row())
            view_idx = self._source_to_view(row0)
            roots_state[key] = {
                "expanded_root": bool(view_idx.isValid() and self.data_store.view.isExpanded(view_idx)),
                "expanded_rel": list(iter_expanded_relative_paths(self.data_store.view, row0)),
            }

        selected_paths = [self._index_path(idx) for idx in selected_source_rows(self.data_store.view) if idx.isValid()]
        current_src = self._proxy_to_source(self.data_store.view.currentIndex())
        if current_src.isValid():
            current_src = self.data_store.model.index(current_src.row(), 0, current_src.parent())
        current_path = self._index_path(current_src) if current_src.isValid() else None
        return {
            "roots": roots_state,
            "selection_before": selected_paths,
            "current_before": current_path,
        }

    @staticmethod
    def _sort_move_paths(paths: list[tuple[tuple[int, ...], int]]) -> list[tuple[tuple[int, ...], int]]:
        return sorted(paths, key=lambda p: (p[0], p[1]))

    def _apply_relative_expansion_mapping(
        self,
        source_roots: list[tuple[tuple[int, ...], int]],
        target_roots: list[tuple[tuple[int, ...], int]],
        roots_state: dict[tuple[tuple[int, ...], int], dict[str, Any]],
    ) -> None:
        ordered_sources = self._sort_move_paths(source_roots)
        for source_root, target_root in zip(ordered_sources, target_roots):
            state = roots_state.get(source_root)
            if state is None:
                continue
            target_parent_path, target_row = target_root
            target_parent = self._index_from_path(target_parent_path)
            target_index = self.data_store.model.index(target_row, 0, target_parent)
            if not target_index.isValid():
                continue
            target_view = self._source_to_view(target_index)
            if target_view.isValid():
                self.data_store.view.setExpanded(target_view, bool(state.get("expanded_root", False)))
            apply_expanded_relative_paths(self.data_store.view, target_index, state.get("expanded_rel", []))

    def _restore_selection_paths(self, paths: list[tuple[int, ...]], current_path: tuple[int, ...] | None) -> None:
        from PySide6.QtCore import QItemSelection, QItemSelectionModel

        sm = self.data_store.view.selectionModel()
        if sm is None:
            return
        selection = QItemSelection()
        first_view_idx = None
        for path in paths:
            src_idx = self._index_from_path(path)
            view_idx = self._source_to_view(src_idx)
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
            src_current = self._index_from_path(current_path)
            view_current = self._source_to_view(src_current)
            if view_current.isValid():
                sm.setCurrentIndex(view_current, QItemSelectionModel.SelectionFlag.NoUpdate)
                return
        if first_view_idx is not None:
            sm.setCurrentIndex(first_view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)

    def _apply_move_view_state(self, cmd: _MoveRowsCmd, *, undo: bool) -> None:
        state = self.data_store._move_view_state_by_cmd_id.get(id(cmd))
        if state is None:
            return
        roots_state = state.get("roots", {})
        if undo:
            self._apply_relative_expansion_mapping(
                cmd.source_paths, self._sort_move_paths(cmd.source_paths), roots_state
            )
            self._restore_selection_paths(state.get("selection_before", []), state.get("current_before"))
            return
        self._apply_relative_expansion_mapping(cmd.source_paths, cmd.placed_paths, roots_state)
        self._restore_selection_at_paths(cmd.placed_paths)

    def _on_undo_index_changed(self, new_index: int) -> None:
        old_index = self.data_store._last_undo_index
        if new_index == old_index:
            return

        if new_index > old_index:
            for i in range(old_index, new_index):
                cmd = self.data_store.undo_stack.command(i)
                if isinstance(cmd, _MoveRowsCmd) and id(cmd) in self.data_store._move_view_state_by_cmd_id:
                    self._apply_move_view_state(cmd, undo=False)
        else:
            for i in range(old_index - 1, new_index - 1, -1):
                cmd = self.data_store.undo_stack.command(i)
                if isinstance(cmd, _MoveRowsCmd) and id(cmd) in self.data_store._move_view_state_by_cmd_id:
                    self._apply_move_view_state(cmd, undo=True)
        self.data_store._last_undo_index = new_index

    # ------------------------------------------------------------------
    # Smart-restore diff helpers
    # ------------------------------------------------------------------

    def _diff_apply(self, item: JsonTreeItem, target: Any, item_index: QModelIndex) -> bool:
        return self.data_store._diff_applier.apply(item, target, item_index)

    # -- low-level mutators used by diff and typed commands --------------

    def _emit_row_changed(self, item_index: QModelIndex) -> None:
        self.data_store._diff_applier.emit_row_changed(item_index)

    def _insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        return self.data_store._diff_applier.insert_typed_item(parent_item, parent_index, position, value, name=name)

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
        """Drive the view's selectionModel so the rows at the given
        ``(parent_path, row)`` tuples are all selected after a move.

        Lifted out of ``_MoveRowsCmd`` so that the undo command stays
        decoupled from the view.
        """
        if not placed:
            return
        from PySide6.QtCore import QItemSelection, QItemSelectionModel

        sm = self.data_store.view.selectionModel()
        if sm is None:
            return
        selection = QItemSelection()
        first_view_idx = None
        for parent_path, row in placed:
            p = self._index_from_path(parent_path)
            src_idx = self.data_store.model.index(row, 0, p)
            view_idx = self._source_to_view(src_idx)
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
        *,
        copy_only: bool = False,
        cut: bool = False,
        paste: bool = False,
        paste_zip: bool = False,
        replace_zip: bool = False,
        delete: bool = False,
        duplicate: bool = False,
        move_up: bool = False,
        move_down: bool = False,
        move_out_up: bool = False,
        move_out_down: bool = False,
        sort_keys: bool = False,
    ) -> None:
        if self.data_store.is_read_only:
            return
        changed = False
        if copy_only:
            changed = copy_selection(self.data_store.view)
        elif cut:
            changed = cut_selection(self.data_store.view)
        elif paste:
            changed = paste_auto(self.data_store.view)
        elif paste_zip:
            changed = paste_insert_after_zip(self.data_store.view)
        elif replace_zip:
            changed = paste_replace_zip(self.data_store.view)
        elif delete:
            changed = delete_selection(self.data_store.view)
        elif duplicate:
            changed = duplicate_selection(self.data_store.view)
        elif move_up:
            changed = move_selection_up(self.data_store.view)
        elif move_down:
            changed = move_selection_down(self.data_store.view)
        elif move_out_up:
            changed = move_selection_out_up(self.data_store.view)
        elif move_out_down:
            changed = move_selection_out_down(self.data_store.view)
        elif sort_keys:
            changed = sort_selection_keys(self.data_store.view, recursive=False)

        if changed:
            self.show_status(success_message, 1500)

    def insert_sibling_before(self) -> bool:
        if self.data_store.is_read_only:
            return False
        return insert_sibling_before(self.data_store.view)

    def insert_sibling_after(self) -> bool:
        if self.data_store.is_read_only:
            return False
        return insert_sibling_after(self.data_store.view)

    def insert_child(self) -> bool:
        if self.data_store.is_read_only:
            return False
        return insert_child_current(self.data_store.view)
