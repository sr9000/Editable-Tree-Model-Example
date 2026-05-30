"""JsonTabData -- per-tab document state container.
Phase I result:  ``JsonTabData`` is the single composition point for the
four per-axis substates a :class:`documents.tab.JsonTab` owns:
* :class:`documents.states.io_controller.IoController` -- file path,
  save format, dirty flag, save/save_as/snapshot (exposed as :attr:`io`).
* :class:`documents.states.view_state.ViewState` -- UI widgets, proxy,
  delegates (exposed as :attr:`view_state`; individual widgets remain
  reachable via :attr:`view`, :attr:`proxy`, etc. property forwards).
* :class:`documents.states.editing_state.EditingState` -- tree model,
  mutation gateway, undo history, affix MRU, last-move-placed cache
  (exposed as :attr:`editing_state`).
* :class:`documents.states.validation_state.ValidationState` -- schema
  source/ref, issue index, auto-rescan timer (exposed as
  :attr:`validation`).
Two stateful controllers that don't fit cleanly into the four axes are
also held here: :attr:`appearance` (font / theme) and
:attr:`editability` (read-only mode).  They surface through their own
typed property forwards (``theme``, ``is_read_only``, ``_font_pt``, ...).
Test reach-in to ``tab.data_store.<attr>`` (61 test files / 27 distinct
attrs) is supported by the property-forward layer below; per Plan 20
section 6 tests stay as they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QLineEdit

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from documents.mutation_gateway import DocumentMutationGateway
from documents.states.editing_state import EditingState
from documents.states.io_controller import IoController
from documents.states.validation_state import ValidationState
from documents.states.view_state import ViewState
from documents.tab_dependencies import JsonTabHost
from documents.tab_history import TabHistoryController
from state.affix_mru import AffixMRU
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
from tree_filter_proxy import TreeFilterProxy
from validation.index import IssueIndex
from validation.schema_registry import SchemaSource
from validation.schema_source import SchemaRef


class EditabilityFacadeProtocol(Protocol):
    @property
    def is_read_only(self) -> bool: ...


class AppearanceFacadeProtocol(Protocol):
    @property
    def theme(self) -> ThemeSpec | None: ...
    @property
    def icon_provider(self) -> IconProvider | None: ...
    @property
    def default_font_pt(self) -> int: ...
    @property
    def font_pt(self) -> int: ...
    @property
    def user_sized_columns(self) -> set[int]: ...
    @property
    def programmatic_column_resize(self) -> bool: ...
    @programmatic_column_resize.setter
    def programmatic_column_resize(self, value: bool) -> None: ...
    @property
    def monospace_fields_enabled(self) -> bool: ...
    @property
    def regular_font_family(self) -> str | None: ...
    @property
    def monospace_font_family(self) -> str | None: ...


@dataclass
class JsonTabData:
    """Per-tab document state composed from four single-responsibility substates.
    See module docstring for the substate inventory.
    """

    # ----- The four substates + two cross-cutting controllers --------------
    view_state: ViewState = field(default_factory=ViewState)
    editing_state: EditingState = field(default_factory=EditingState)
    io: IoController | None = None
    validation: ValidationState | None = None
    editability: EditabilityFacadeProtocol | None = None
    appearance: AppearanceFacadeProtocol | None = None
    _host: JsonTabHost | None = None

    # ----- Host shortcuts (unchanged from former JsonTabDataFacade) --------
    def refresh_actions(self) -> None:
        if self._host is not None:
            self._host.refresh_actions()

    def show_permanent_message(self, message: str) -> None:
        if self._host is not None:
            self._host.show_permanent_message(message)

    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        if self._host is not None:
            self._host.show_status_message(message, timeout_ms)

    # ----- ViewState forwards (read+write) ---------------------------------
    @property
    def ui(self) -> Ui_JsonTab | None:
        return self.view_state.ui

    @ui.setter
    def ui(self, value: Ui_JsonTab | None) -> None:
        self.view_state.ui = value

    @property
    def view(self) -> JsonTreeView | None:
        return self.view_state.view

    @view.setter
    def view(self, value: JsonTreeView | None) -> None:
        self.view_state.view = value

    @property
    def search_edit(self) -> QLineEdit | None:
        return self.view_state.search_edit

    @search_edit.setter
    def search_edit(self, value: QLineEdit | None) -> None:
        self.view_state.search_edit = value

    @property
    def proxy(self) -> TreeFilterProxy | None:
        return self.view_state.proxy

    @proxy.setter
    def proxy(self, value: TreeFilterProxy | None) -> None:
        self.view_state.proxy = value

    @property
    def name_delegate(self) -> NameDelegate | None:
        return self.view_state.name_delegate

    @name_delegate.setter
    def name_delegate(self, value: NameDelegate | None) -> None:
        self.view_state.name_delegate = value

    @property
    def type_delegate(self) -> JsonTypeDelegate | None:
        return self.view_state.type_delegate

    @type_delegate.setter
    def type_delegate(self, value: JsonTypeDelegate | None) -> None:
        self.view_state.type_delegate = value

    @property
    def value_delegate(self) -> ValueDelegate | None:
        return self.view_state.value_delegate

    @value_delegate.setter
    def value_delegate(self, value: ValueDelegate | None) -> None:
        self.view_state.value_delegate = value

    # ----- EditingState forwards (read+write) ------------------------------
    @property
    def model(self) -> JsonTreeModel | None:
        return self.editing_state.model

    @model.setter
    def model(self, value: JsonTreeModel | None) -> None:
        self.editing_state.model = value

    @property
    def mutations(self) -> DocumentMutationGateway | None:
        return self.editing_state.mutations

    @mutations.setter
    def mutations(self, value: DocumentMutationGateway | None) -> None:
        self.editing_state.mutations = value

    @property
    def affix_mru(self) -> AffixMRU | None:
        return self.editing_state.affix_mru

    @affix_mru.setter
    def affix_mru(self, value: AffixMRU | None) -> None:
        self.editing_state.affix_mru = value

    @property
    def history(self) -> TabHistoryController | None:
        return self.editing_state.history

    @history.setter
    def history(self, value: TabHistoryController | None) -> None:
        self.editing_state.history = value

    @property
    def _last_move_placed(self) -> list[tuple[tuple[int, ...], int]]:
        return self.editing_state.last_move_placed

    @_last_move_placed.setter
    def _last_move_placed(self, value: list[tuple[tuple[int, ...], int]]) -> None:
        self.editing_state.last_move_placed = value

    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]:
        return self.editing_state.last_move_placed

    # ----- IoController forwards (read+write) ------------------------------
    @property
    def file_path(self) -> str | None:
        return self.io.file_path if self.io is not None else None

    @file_path.setter
    def file_path(self, value: str | None) -> None:
        if self.io is not None:
            self.io.file_path = value

    @property
    def save_format(self) -> str | None:
        return self.io.save_format if self.io is not None else None

    @save_format.setter
    def save_format(self, value: str | None) -> None:
        if self.io is not None:
            self.io.save_format = value

    @property
    def is_dirty(self) -> bool:
        return self.io.dirty if self.io is not None else False

    # ----- ValidationState forwards (read-only) ----------------------------
    @property
    def schema(self) -> dict[str, Any] | None:
        return self.validation.schema if self.validation is not None else None

    @property
    def schema_ref(self) -> SchemaRef | None:
        return self.validation.schema_ref if self.validation is not None else None

    @property
    def schema_source(self) -> SchemaSource | None:
        return self.validation.schema_source if self.validation is not None else None

    @property
    def issue_index(self) -> IssueIndex | None:
        return self.validation.issue_index if self.validation is not None else None

    @property
    def auto_rescan(self) -> bool:
        return self.validation.auto_rescan if self.validation is not None else False

    # ----- History forwards (read-only mostly) -----------------------------
    @property
    def undo_stack(self) -> QUndoStack | None:
        return self.history.undo_stack if self.history is not None else None

    @property
    def _move_view_state_by_cmd_id(self) -> dict[int, dict[str, Any]] | None:
        return self.history._move_view_state_by_cmd_id if self.history is not None else None

    @property
    def _last_undo_index(self) -> int:
        return self.history.last_undo_index if self.history is not None else 0

    @_last_undo_index.setter
    def _last_undo_index(self, value: int) -> None:
        if self.history is not None:
            self.history.last_undo_index = value

    # ----- Editability / appearance forwards -------------------------------
    @property
    def is_read_only(self) -> bool:
        return self.editability.is_read_only if self.editability is not None else False

    @property
    def theme(self) -> ThemeSpec | None:
        return self.appearance.theme if self.appearance is not None else None

    @property
    def icon_provider(self) -> IconProvider | None:
        return self.appearance.icon_provider if self.appearance is not None else None

    @property
    def _default_font_pt(self) -> int:
        return self.appearance.default_font_pt if self.appearance is not None else 10

    @property
    def _font_pt(self) -> int:
        return self.appearance.font_pt if self.appearance is not None else 10

    @property
    def _user_sized_columns(self) -> set[int]:
        return self.appearance.user_sized_columns if self.appearance is not None else set()

    @property
    def _programmatic_column_resize(self) -> bool:
        return self.appearance.programmatic_column_resize if self.appearance is not None else False

    @_programmatic_column_resize.setter
    def _programmatic_column_resize(self, value: bool) -> None:
        if self.appearance is not None:
            self.appearance.programmatic_column_resize = value

    @property
    def _monospace_fields_enabled(self) -> bool:
        return self.appearance.monospace_fields_enabled if self.appearance is not None else False

    @property
    def _regular_font_family(self) -> str | None:
        return self.appearance.regular_font_family if self.appearance is not None else None

    @property
    def _monospace_font_family(self) -> str | None:
        return self.appearance.monospace_font_family if self.appearance is not None else None
