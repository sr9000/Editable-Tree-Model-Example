from __future__ import annotations

import base64
import gzip
import os
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import gmpy2
from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPersistentModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QWidget

from documents.mutation_gateway import DocumentMutationGateway
from documents.tab_data import JsonTabData
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
from state.affix_mru import AffixMRU
from state.view_state import apply_expanded_relative_paths, iter_expanded_relative_paths
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model_roles import VALIDATION_SEVERITY_ROLE
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
from undo.diff import DiffApplier
from units.number_affix import NumberAffix
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.json_pointer import instance_path_to_model_path
from validation.schema_registry import SchemaSource
from validation.schema_source import SchemaRef

def _make_label(text: str, target_qname: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    return f"[{timestamp}] {text} @ {target_qname}"


_DEFAULT_DATA = object()

# QUndoCommand.id() values for typed commands that support mergeWith().
# Qt requires id() to fit in a signed 32-bit int (anything larger overflows
# the C++ ``int`` return type and raises ``SystemError`` from PySide).
_CMD_ID_RENAME = 0x0E71_0001
_CMD_ID_EDIT_VALUE = 0x0E71_0002

# Time window in seconds during which two consecutive same-path edits
# collapse into one undo entry. Tuned for keystroke-level typing.
_MERGE_WINDOW_SECONDS = 0.5


def _demo_data() -> dict[str, Any]:
    return {
        "question": "The Ultimate Question of Life, the Universe, and Everything.",
        "answer": 42,
        "integer": 9223372036854775808,
        "int units": "10 m/s",
        "float units": "3.45s",
        "int currency": "$10",
        "float currency": "lvl 2.5",
        "float": gmpy2.mpq("3.14"),
        "percent": gmpy2.mpq("50/100"),
        "single-line": "Hello, world!" * 100,
        "utf8-line": "caf\u00e9",
        "multi-line": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6",
        "utf8-text": "Line 1\nLine 2\n\u03a9",
        "password": "plainsecret",
        "private_key": "-----BEGIN KEY-----\nabc\n-----END KEY-----",
        "bytes": base64.b64encode(b"hello " * 10).decode(),
        "zlib": base64.b64encode(zlib.compress(b"hello " * 10)).decode(),
        "gzip": base64.b64encode(gzip.compress(b"hello " * 10)).decode(),
        "date": "2024-06-01",
        "time": "12:34",
        "datetime": "2024-06-01 12:34:56",
        "datetime-utc": "2024-06-01T12:34:56Z",
        "dt+timezone": "2024-06-01T12:34:56.9999+00:00",
        "boolean": True,
        "object": {"key": "value"},
        "array": [1, 2, 3],
        "null": None,
        "color rgb": "#3498db",
        "color rgba": "#3498db80",
        # Pseudo text types — content-derived labels that appear automatically
        # when a string value is empty or whitespace-only.
        "empty string": "",  # → EMPTY_STRING
        "ws ascii": "   ",  # → WS_STRING (ASCII spaces only)
        "ws unicode": " \u00a0 ",  # → WS_UNICODE (includes NBSP)
        "ws multiline": "  \n  ",  # → WS_MULTILINE (whitespace + newline)
        "ws text": " \u00a0\n ",  # → WS_TEXT  (non-ASCII WS + newline)
    }


class JsonTab(QWidget):
    _navigation: JsonTabNavigationController | None = None
    _editability: JsonTabEditabilityController | None = None

    dirtyChanged = Signal(bool)
    schemaChanged = Signal(object)
    validationChanged = Signal(object)

    def eventFilter(self, watched, event):  # type: ignore[override]
        navigation = self._navigation
        if navigation is not None and navigation.handle_event_filter(watched, event):
            return True
        return super().eventFilter(watched, event)

    def _toggle_current_row_expansion_with_space(self) -> None:
        navigation = self._navigation
        if navigation is not None:
            navigation.toggle_current_row_expansion_with_space()

    def _handle_arrow_navigation(self, key: int | Qt.Key, modifiers: Qt.KeyboardModifier) -> bool:
        navigation = self._navigation
        return navigation is not None and navigation.handle_arrow_navigation(key, modifiers)

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
        self._navigation = JsonTabNavigationController(self.data_store, self.edit_name_or_value_from_enter)
        self._editability = JsonTabEditabilityController(self.data_store)

        # All parts stored inside self.data_store are populated here:
        self.data_store.ui = None
        self.data_store.view = None
        self.data_store.search_edit = None
        self.data_store._default_font_pt = 10
        self.data_store._font_pt = 10
        self.data_store._user_sized_columns = set()
        self.data_store._programmatic_column_resize = False

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
        self.data_store._theme = resolved_services.theme
        self.data_store._icon_provider = resolved_services.icon_provider
        self.data_store._read_only = False
        self.data_store._monospace_fields_enabled = False
        self.data_store._regular_font_family = None
        self.data_store._monospace_font_family = None
        self.data_store._last_move_placed = []

        init_layout(self)
        self._editability.capture_editable_view_state()
        self._sync_icon_size_with_font()

        # option to edit headers is not needed
        # self.header_editor = HeaderViewEditorMixin(self.data_store.view.header())

        if data is _DEFAULT_DATA:
            model_data = _demo_data()
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
        root_data = self.data_store.model.root_item.to_json()
        model_path = instance_path_to_model_path(root_data, issue.instance_path)
        if model_path is None:
            self.show_status("Validation issue path no longer exists", 2000)
            return False

        source_row = self._index_from_path(model_path)
        if not source_row.isValid():
            self.show_status("Validation issue path no longer exists", 2000)
            return False

        source_row = source_row.siblingAtColumn(0)
        view_row = self._source_to_view(source_row)
        if not view_row.isValid():
            self.show_status("Validation issue path no longer exists", 2000)
            return False

        sm = self.data_store.view.selectionModel()
        if sm is not None:
            sm.select(
                view_row,
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )
            sm.setCurrentIndex(view_row, QItemSelectionModel.SelectionFlag.NoUpdate)

        self.data_store.view.setCurrentIndex(view_row)
        self.data_store.view.scrollTo(view_row, QAbstractItemView.ScrollHint.PositionAtCenter)

        if not edit:
            return True

        source_value = source_row.siblingAtColumn(2)
        if not source_value.isValid():
            return True
        if not (self.data_store.model.flags(source_value) & Qt.ItemFlag.ItemIsEditable):
            return True

        view_value = self._source_to_view(source_value)
        if not view_value.isValid():
            return True
        self.data_store.view.setCurrentIndex(view_value)
        self.data_store.view.edit(view_value)
        return True

    def _severity_provider(self, model_path: tuple[int, ...]) -> str | None:
        """Lazily queried by the model for VALIDATION_SEVERITY_ROLE."""
        return self.data_store.validation.severity_for(model_path)

    def _on_validation_changed(self, _index: IssueIndex) -> None:
        """Emit recursive dataChanged so all visible rows repaint their badges."""

        def _emit_ranges(parent: QModelIndex) -> None:
            rows = self.data_store.model.rowCount(parent)
            if rows <= 0:
                return
            top_left = self.data_store.model.index(0, 0, parent)
            bottom_right = self.data_store.model.index(rows - 1, self.data_store.model.columnCount(parent) - 1, parent)
            self.data_store.model.dataChanged.emit(top_left, bottom_right, [VALIDATION_SEVERITY_ROLE])
            for row in range(rows):
                _emit_ranges(self.data_store.model.index(row, 0, parent))

        _emit_ranges(QModelIndex())

    def set_theme(self, theme: ThemeSpec, icon_provider: IconProvider | None = None) -> None:
        self.data_store._theme = theme
        self.data_store._icon_provider = icon_provider or self.data_store._icon_provider
        self.data_store.name_delegate.set_theme(theme)
        self.data_store.value_delegate.set_theme(theme)
        self.data_store.type_delegate.set_theme(theme)
        self.data_store.type_delegate.set_icon_provider(self.data_store._icon_provider)
        self.data_store.model.set_icon_provider(self.data_store._icon_provider)

        roles = [
            Qt.ItemDataRole.ForegroundRole,
            Qt.ItemDataRole.BackgroundRole,
            Qt.ItemDataRole.FontRole,
            Qt.ItemDataRole.DecorationRole,
        ]

        def emit_ranges(parent: QModelIndex) -> None:
            rows = self.data_store.model.rowCount(parent)
            if rows <= 0:
                return

            top_left = self.data_store.model.index(0, 0, parent)
            bottom_right = self.data_store.model.index(rows - 1, self.data_store.model.columnCount(parent) - 1, parent)
            self.data_store.model.dataChanged.emit(top_left, bottom_right, roles)

            for row in range(rows):
                child_parent = self.data_store.model.index(row, 0, parent)
                emit_ranges(child_parent)

        emit_ranges(QModelIndex())

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self.data_store._monospace_fields_enabled == enabled:
            return
        self.data_store._monospace_fields_enabled = enabled
        self.data_store.name_delegate.set_monospace_fields_enabled(enabled)
        self.data_store.value_delegate.set_monospace_fields_enabled(enabled)
        self.data_store.view.viewport().update()

    def set_regular_font_family(self, family: str) -> None:
        if not family:
            return
        family = str(family)
        if self.data_store._regular_font_family == family:
            return
        self.data_store._regular_font_family = family
        font = self.data_store.view.font()
        font.setFamily(family)
        if font.pointSizeF() <= 0:
            font.setPointSize(max(6, int(self.data_store._font_pt or 10)))
        self.data_store.view.setFont(font)
        self._sync_icon_size_with_font()

    def set_monospace_font_family(self, family: str) -> None:
        if not family:
            return
        family = str(family)
        if self.data_store._monospace_font_family == family:
            return
        self.data_store._monospace_font_family = family
        self.data_store.name_delegate.set_monospace_font_family(family)
        self.data_store.value_delegate.set_monospace_font_family(family)
        self.data_store.view.viewport().update()

    def set_editor_font_point_size(self, point_size: int) -> None:
        old_pt = self.data_store._font_pt
        self._set_font_pt(point_size)
        self._scale_columns_for_font(old_pt, self.data_store._font_pt)

    def apply_font_profile(self, profile) -> None:
        """Aspect entry point called by ``FontController``.

        Order matters: family must be set before point size so the column
        scaler sees the final font width, and the monospace toggle must
        come last because it triggers a viewport repaint that picks up
        the freshly-installed delegate fonts.
        """
        if profile.regular_family:
            self.set_regular_font_family(profile.regular_family)
        self.set_editor_font_point_size(profile.editor_point_size)
        if profile.monospace_family:
            self.set_monospace_font_family(profile.monospace_family)
        self.set_monospace_fields_enabled(profile.monospace_fields_enabled)

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
        self.data_store._programmatic_column_resize = True
        try:
            for col in (0, 1):
                if force or col not in self.data_store._user_sized_columns:
                    self.data_store.view.resizeColumnToContents(col)
        finally:
            self.data_store._programmatic_column_resize = False

    def _scale_columns_for_font(self, old_pt: int, new_pt: int) -> None:
        """Proportionally scale name/type column widths when the font changes.

        Columns the user has hand-resized are left alone.  The value column
        (col 2) is never touched because it is set to stretch.
        """
        if old_pt <= 0 or new_pt <= 0 or old_pt == new_pt:
            return
        scale = new_pt / old_pt
        self.data_store._programmatic_column_resize = True
        try:
            for col in (0, 1):
                if col in self.data_store._user_sized_columns:
                    continue  # respect the user's manual choice
                current = self.data_store.view.columnWidth(col)
                new_w = max(20, min(2000, int(current * scale)))
                self.data_store.view.setColumnWidth(col, new_w)
        finally:
            self.data_store._programmatic_column_resize = False

    def _set_font_pt(self, pt: int) -> None:
        clamped = max(6, min(48, int(pt)))
        self.data_store._font_pt = clamped
        font = self.data_store.view.font()
        font.setPointSize(clamped)
        self.data_store.view.setFont(font)
        self._sync_icon_size_with_font()

    def _sync_icon_size_with_font(self) -> None:
        # Keep type-column icons visually in step with the active tree font.
        px = max(12, min(64, int(round(self.data_store.view.fontMetrics().height() * 1.1))))
        self.data_store.view.setIconSize(QSize(px, px))

    def zoom_in(self) -> None:
        old_pt = self.data_store._font_pt
        self._set_font_pt(self.data_store._font_pt + 1)
        self._scale_columns_for_font(old_pt, self.data_store._font_pt)

    def zoom_out(self) -> None:
        old_pt = self.data_store._font_pt
        self._set_font_pt(self.data_store._font_pt - 1)
        self._scale_columns_for_font(old_pt, self.data_store._font_pt)

    def zoom_reset(self) -> None:
        old_pt = self.data_store._font_pt
        self._set_font_pt(self.data_store._default_font_pt)
        self._scale_columns_for_font(old_pt, self.data_store._font_pt)

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

    def _clear_children(self, item: JsonTreeItem, item_index: QModelIndex) -> None:
        self.data_store._diff_applier.clear_children(item, item_index)

    def _convert_container(
        self,
        item: JsonTreeItem,
        item_index: QModelIndex,
        new_type: JsonType,
        value: Any,
    ) -> None:
        self.data_store._diff_applier.convert_container(item, item_index, new_type, value)

    def _convert_to_leaf(self, item: JsonTreeItem, item_index: QModelIndex, target: Any) -> None:
        self.data_store._diff_applier.convert_to_leaf(item, item_index, target)

    def _insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        return self.data_store._diff_applier.insert_typed_item(parent_item, parent_index, position, value, name=name)

    def _diff_object(self, item: JsonTreeItem, target_dict: dict, item_index: QModelIndex) -> bool:
        return self.data_store._diff_applier.diff_object(item, target_dict, item_index)

    def _diff_array(self, item: JsonTreeItem, target_list: list, item_index: QModelIndex) -> bool:
        return self.data_store._diff_applier.diff_array(item, target_list, item_index)

    def commit_set_data(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        return self.data_store.mutations.commit_set_data(index, value, role)

    # ------------------------------------------------------------------
    # Typed-command public API (action/compensation, no full-tree snapshot)
    # ------------------------------------------------------------------

    def push_move_row(self, parent_index: QModelIndex, src: int, dst: int, *, label: str = "move row") -> bool:
        if self.data_store._read_only:
            return False
        if src == dst:
            return False
        parent_item = self.data_store.model.get_item(parent_index)
        n = parent_item.child_count()
        if not (0 <= src < n and 0 <= dst < n):
            return False
        source_idx = self.data_store.model.index(src, 0, parent_index)
        # push_move_rows uses pre-pop target_row; dst is post-pop.
        # Forward move (src < dst): removing src shifts later rows down by 1,
        # so pre-pop target = dst + 1 to land at the same final position.
        # Backward move (src > dst): no shift needed, pre-pop target = dst.
        pre_pop_target = dst + 1 if src < dst else dst
        return self.push_move_rows(
            [source_idx],
            parent_index,
            pre_pop_target,
            label=label,
        )

    def push_move_rows_anchor(
        self,
        sources: list,
        anchor: "MoveAnchor",  # noqa: F821 — imported lazily below
        *,
        label: str = "move rows",
    ) -> bool:
        """Move *sources* (list of source ``QModelIndex``) to the gap
        described by ``anchor`` as a single undo command.

        Returns ``False`` when:
        - *sources* is empty,
        - any source would become an ancestor of ``anchor.parent_path``
          (cycle guard), or
        - the move is a no-op (block already lands at the anchor).
        """
        from tree_actions.anchors import anchor_is_cycle, anchor_is_no_op, resolve_anchor_insert_row

        if self.data_store._read_only:
            return False
        if not sources:
            return False

        # Snapshot every source's (parent_path, row) BEFORE any mutation.
        source_paths: list[tuple[tuple, int]] = []
        source_names: list[Any] = []
        for idx in sources:
            row0 = self.data_store.model.index(idx.row(), 0, idx.parent())
            source_paths.append((self._index_path(row0.parent()), row0.row()))
            source_names.append(self.data_store.model.get_item(row0).name)

        # Cycle guard.
        if anchor_is_cycle(anchor, source_paths):
            self.show_status("Cannot move a parent into its own descendant", 3000)
            return False

        # No-op guard (path-only). For at_end, resolve to a concrete row first
        # and compare against the would-be insert position.
        if anchor_is_no_op(anchor, source_paths):
            return False
        if anchor.is_at_end:
            insert_row = resolve_anchor_insert_row(self.data_store.model, self, anchor, source_paths)
            same_parent_sources = sorted(r for p, r in source_paths if p == anchor.parent_path)
            if same_parent_sources:
                parent_index = self._index_from_path(anchor.parent_path)
                parent_count = self.data_store.model.rowCount(parent_index)
                last_src = same_parent_sources[-1]
                is_contiguous = all(b - a == 1 for a, b in zip(same_parent_sources, same_parent_sources[1:]))
                # If the block is contiguous and already sits as the suffix,
                # at_end is a no-op.
                if is_contiguous and last_src == parent_count - 1 and len(same_parent_sources) == len(source_paths):
                    return False

        # Build the command.
        move_view_state = self._capture_move_view_state(sources)
        target_qname = self._qualified_name(self.data_store.model.index(sources[0].row(), 0, sources[0].parent()))
        cmd = _MoveRowsCmd(self, _make_label(label, target_qname), source_paths, source_names, anchor)
        self.data_store.undo_stack.push(cmd)
        self.data_store._move_view_state_by_cmd_id[id(cmd)] = move_view_state
        # Expose placed paths for action-layer post-hooks (esp. macros).
        self.data_store._last_move_placed = cmd.placed_paths
        self._apply_move_view_state(cmd, undo=False)
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

        if self.data_store._read_only:
            return False
        if not sources:
            return False
        anchor = pre_pop_target_row_to_anchor(self, target_parent, target_row)
        return self.push_move_rows_anchor(sources, anchor, label=label)

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
        if self.data_store._read_only:
            return False
        if not name_index.isValid() or name_index.column() != 0:
            return False
        item = self.data_store.model.get_item(name_index)
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
        target_qname = self._qualified_name(name_index)
        cmd = _RenameCmd(self, _make_label(label, target_qname), self._index_path(name_index), item.name, candidate)
        self.data_store.undo_stack.push(cmd)
        return True

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        if self.data_store._read_only:
            return False
        if not value_index.isValid() or value_index.column() != 2:
            return False
        name_idx = self.data_store.model.index(value_index.row(), 0, value_index.parent())
        item = self.data_store.model.get_item(name_idx)
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
        target_qname = self._qualified_name(name_idx)
        cmd = _EditValueCmd(self, _make_label(label, target_qname), self._index_path(name_idx), old_subtree, applied)
        self.data_store.undo_stack.push(cmd)
        return True

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
        if self.data_store._read_only:
            return False
        if not type_index.isValid() or type_index.column() != 1:
            return False
        try:
            target_type = new_type if isinstance(new_type, JsonType) else JsonType(str(new_type))
        except ValueError:
            return False
        name_idx = self.data_store.model.index(type_index.row(), 0, type_index.parent())
        item = self.data_store.model.get_item(name_idx)
        if item.json_type is target_type:
            return False
        warn_fraction_loss = self._would_drop_fraction_on_type_change(item, target_type)
        old_subtree = item.to_json()
        old_explicit = item.explicit_type
        old_type = item.json_type
        target_qname = self._qualified_name(name_idx)
        cmd = _ChangeTypeCmd(
            self,
            _make_label(label, target_qname),
            self._index_path(name_idx),
            old_subtree,
            old_explicit,
            old_type,
            target_type,
        )
        self.data_store.undo_stack.push(cmd)
        if warn_fraction_loss:
            self.show_status("Fractional part discarded during float-to-integer conversion", 3000)
        return True

    @staticmethod
    def _is_integer_number_type(json_type: JsonType) -> bool:
        return json_type in (JsonType.INTEGER, JsonType.INTEGER_CURRENCY, JsonType.INTEGER_UNITS)

    @staticmethod
    def _is_float_number_type(json_type: JsonType) -> bool:
        return json_type in (JsonType.FLOAT, JsonType.PERCENT, JsonType.FLOAT_CURRENCY, JsonType.FLOAT_UNITS)

    @classmethod
    def _would_drop_fraction_on_type_change(cls, item: JsonTreeItem, target_type: JsonType) -> bool:
        if not cls._is_integer_number_type(target_type) or not cls._is_float_number_type(item.json_type):
            return False
        source_value = item.value.number if isinstance(item.value, NumberAffix) else item.value
        try:
            q = gmpy2.mpq(str(source_value))
        except (TypeError, ValueError):
            return False
        return q.denominator != 1

    def push_insert_rows(self, inserts: list, *, label: str = "insert", target_qname: str | None = None) -> bool:
        """``inserts`` is a list of ``{parent_path, row, value, name}``."""
        if self.data_store._read_only:
            return False
        if not inserts:
            return False
        qname = (
            target_qname
            if target_qname is not None
            else self._qualified_name(self._index_from_path(inserts[0]["parent_path"]))
        )
        cmd = _InsertRowsCmd(self, _make_label(label, qname), inserts)
        self.data_store.undo_stack.push(cmd)
        return True

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        if self.data_store._read_only:
            return False
        if not indexes:
            return False
        ordered = sorted(indexes, key=lambda i: (self._index_path(i.parent()), i.row()), reverse=True)
        removals = []
        for idx in ordered:
            row0 = self.data_store.model.index(idx.row(), 0, idx.parent())
            item = self.data_store.model.get_item(row0)
            removals.append(
                {
                    "parent_path": self._index_path(idx.parent()),
                    "row": idx.row(),
                    "name": item.name,
                    "value": item.to_json(),
                }
            )
        target_qname = self._qualified_name(ordered[0])
        cmd = _RemoveRowsCmd(self, _make_label(label, target_qname), removals)
        self.data_store.undo_stack.push(cmd)
        return True

    def push_sort_keys(self, index: QModelIndex, *, recursive: bool = False, label: str | None = None) -> bool:
        if self.data_store._read_only:
            return False
        if not index.isValid():
            return False
        item = self.data_store.model.get_item(index)
        if item.json_type is not JsonType.OBJECT:
            return False
        old_subtree = item.to_json()
        if not recursive and list(old_subtree.keys()) == sorted(old_subtree.keys()):
            return False
        target_qname = self._qualified_name(index)
        text = label if label is not None else ("sort keys recursive" if recursive else "sort keys")
        cmd = _SortKeysCmd(self, _make_label(text, target_qname), self._index_path(index), old_subtree, recursive)
        self.data_store.undo_stack.push(cmd)
        return True

    def push_switch_field_case(
        self,
        renames: list[dict[str, Any]],
        *,
        label: str = "switch field case",
        target_qname: str | None = None,
    ) -> bool:
        if self.data_store._read_only:
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
            idx = self._index_from_path(path)
            if not idx.isValid():
                continue
            item = self.data_store.model.get_item(idx)
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
            parent_index = self._index_from_path(parent_path)
            parent_item = self.data_store.model.get_item(parent_index)
            final_names: list[str] = []
            for row, child in enumerate(parent_item.child_items):
                if not isinstance(child.name, str):
                    continue
                final_names.append(updates.get(row, child.name))
            if len(set(final_names)) != len(final_names):
                return False

        first_index = self._index_from_path(normalized[0]["path"])
        qname = target_qname if target_qname is not None else self._qualified_name(first_index)
        cmd = _SwitchFieldCaseCmd(self, _make_label(label, qname), normalized)
        self.data_store.undo_stack.push(cmd)
        return True

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
        if self.data_store._read_only:
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
        if self.data_store._read_only:
            return False
        return insert_sibling_before(self.data_store.view)

    def insert_sibling_after(self) -> bool:
        if self.data_store._read_only:
            return False
        return insert_sibling_after(self.data_store.view)

    def insert_child(self) -> bool:
        if self.data_store._read_only:
            return False
        return insert_child_current(self.data_store.view)
