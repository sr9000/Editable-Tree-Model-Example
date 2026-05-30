from __future__ import annotations

import os
from typing import Any, Callable

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

from documents import tab_init
from documents.mutation_gateway import DocumentMutationGateway
from documents.states.editing_controller import TreeAction
from documents.tab_appearance import JsonTabAppearanceController
from documents.tab_data import JsonTabData
from documents.tab_dependencies import JsonTabServices
from documents.tab_editability import JsonTabEditabilityController
from documents.tab_marker import JsonTabWidgetMarker
from documents.tab_navigation import JsonTabNavigationController
from documents.tab_status import on_current_changed, size_hint_for_item
from documents.tab_validation import TabValidationController
from documents.tab_validation_view import JsonTabValidationViewController
from documents.view_controller import ViewController
from state.affix_mru import AffixMRU
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
from undo.commands import _ChangeTypeCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _EditValueCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _InsertRowsCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _RemoveRowsCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _RenameCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _SortKeysCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _SwitchFieldCaseCmd  # noqa: F401 — re-exported for test imports
from undo.commands import _MoveRowsCmd
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
    _view_controller: ViewController | None = None

    dirtyChanged = Signal(bool)
    schemaChanged = Signal(object)
    validationChanged = Signal(object)

    data_store: JsonTabData = None  # populated by tab_init.bootstrap

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

    # -- Phase I (I5): direct substate accessors -------------------
    # ``JsonTab directly composes the four states.``  These read-only
    # properties expose each substate object so callers inside
    # ``documents/`` can grab a whole axis instead of dereferencing
    # individual ``data_store.<attr>`` fields.  External callers
    # continue to use the per-attribute typed forwards above.
    @property
    def io(self):
        """The :class:`documents.states.io_controller.IoController` substate."""
        return self.data_store.io

    @property
    def view_state(self):
        """The :class:`documents.states.view_state.ViewState` substate."""
        return self.data_store.view_state

    @property
    def editing_state(self):
        """The :class:`documents.states.editing_controller.EditingController` substate."""
        return self.data_store.editing_state

    @property
    def editing(self):
        """The :class:`documents.states.editing_controller.EditingController`.

        Active controller owning the editing axis (tree model, mutation
        gateway, undo history, affix MRU, last-move cache) and the typed
        ``push_*`` command behaviour; see Plan 21 Phase N.
        """
        return self.data_store.editing_state

    @property
    def validation_state(self):
        """The :class:`documents.states.validation_state.ValidationState` substate.

        Same object as :attr:`validation`; the alias name matches the
        I1-I4 ``*State`` naming scheme.
        """
        return self.data_store.validation

    # -- Phase C: typed file-state accessors ---------------------
    # Plan 21 L3 retired the per-attribute ``file_path`` / ``save_format``
    # / ``is_dirty`` forwards; external callers reach those through the
    # IoController (``tab.io.file_path`` / ``.save_format`` / ``.dirty``).
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

    @property
    def view_controller(self) -> ViewController:
        """Selection / expansion / scroll controller for the tree view.

        Created by :func:`documents.tab_init.bootstrap`. External callers
        should prefer this over :attr:`view` whenever the underlying
        operation is selection-, expansion-, or scroll-related; see
        ``plans/20-decouple-jsontab.md`` Phase D (D1) and
        ``plans/21-promote-substates-to-controllers.md`` Phase M (M1).
        """
        assert self._view_controller is not None, "view_controller accessed before bootstrap"
        return self._view_controller

    @property
    def model(self) -> JsonTreeModel:
        """Typed accessor for the underlying tree model.

        Replaces ``tab.data_store.model`` for external callers; see
        ``plans/20-decouple-jsontab.md`` Phase E (E-light). For the
        17 non-``undo/`` sites that only needed structural reads,
        prefer the narrow helpers below (Phase E, E2): :meth:`root_data`,
        :meth:`root_index`, :meth:`root_item`, :meth:`row_count`,
        :meth:`column_count`. Raw ``.model`` access remains the right
        tool for ``undo/`` where the full ``QAbstractItemModel`` API
        is genuinely needed; Phase H will retire those last usages
        through the path-based mutation gateway.
        """
        return self.data_store.model

    # -- Phase E (E2): narrow read helpers covering the structural /
    # data-read intents identified in reports/model_access_audit.md.
    # These let callers in app/, state/, tree_actions/ depend on a
    # tiny stable surface instead of the full QAbstractItemModel.
    def root_index(self) -> QModelIndex:
        """Return the index of the root row.

        When ``model.show_root`` is False the document is rendered as
        an implicit top-level container; in that case the conventional
        ``root index`` for traversal is the invalid index, since
        :meth:`JsonTreeModel.get_item` maps the invalid index to the
        real ``root_item``.
        """
        model = self.data_store.model
        if not model.show_root:
            return QModelIndex()
        return model.index(0, 0, QModelIndex())

    def root_item(self) -> JsonTreeItem:
        """Return the root :class:`JsonTreeItem` of the document tree."""
        return self.data_store.model.root_item

    def root_data(self) -> Any:
        """Return a fresh JSON-serialisable snapshot of the document root."""
        return self.data_store.model.root_item.to_json()

    def row_count(self, parent: QModelIndex = QModelIndex()) -> int:
        """Number of children directly under ``parent``."""
        return self.data_store.model.rowCount(parent)

    def column_count(self) -> int:
        """Number of columns in the document model (Name / Type / Value)."""
        return self.data_store.model.columnCount()

    # -- Phase E (E2/E3): viewport + zoom helpers consolidating the
    # last bits of underscore-prefixed reach-in from state/view_state.py.
    @property
    def zoom_pt(self) -> int:
        """Per-tab editor font point-size override (0 ⇒ inherit global)."""
        return self.data_store._font_pt

    # -- Phase F long tail (F4 / F5): typed accessors for residual
    # state still leaked into tree_actions/, app/, undo/.
    @property
    def search_edit(self) -> QLineEdit:
        return self.data_store.search_edit

    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]:
        return self.data_store.last_move_placed

    @property
    def issue_index(self) -> IssueIndex | None:
        return self.data_store.issue_index

    @property
    def affix_mru(self) -> AffixMRU:
        return self.data_store.affix_mru

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
        self.editing.on_type_changed(item_index, lossy)

    def _reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        self.editing.reopen_value_editor(value_pindex)

    def edit_name_or_value_from_enter(self) -> None:
        self.editing.edit_name_or_value_from_enter()

    def _open_active_type_combo_popup(self) -> None:
        self.editing.open_active_type_combo_popup()

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
        return self.io.save()

    def save_as(self, path: str | None = None) -> bool:
        return self.io.save_as(path=path)

    def _snapshot(self) -> Any:
        return self.io.snapshot()

    def _size_hint_for_item(self, item: JsonTreeItem) -> str | None:
        return size_hint_for_item(item)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        on_current_changed(self, current, _previous)

    def _run_tree_action(
        self,
        success_message: str,
        actions: set[TreeAction],
    ) -> None:
        self.editing.run_tree_action(success_message, actions)
