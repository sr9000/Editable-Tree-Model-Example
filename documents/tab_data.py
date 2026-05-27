from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLineEdit

    from delegates.name_delegate import NameDelegate
    from delegates.type_delegate import JsonTypeDelegate
    from delegates.value import ValueDelegate
    from documents.json_tab_ui import Ui_JsonTab
    from documents.mutation_gateway import DocumentMutationGateway
    from state.affix_mru import AffixMRU
    from themes.icon_provider import IconProvider
    from themes.spec import ThemeSpec
    from tree.model import JsonTreeModel
    from tree.view import JsonTreeView
    from tree_filter_proxy import TreeFilterProxy
    from validation.schema_registry import SchemaSource
    from validation.schema_source import SchemaRef


@dataclass
class JsonTabData:
    ui: Ui_JsonTab | None = None
    view: JsonTreeView | None = None
    search_edit: QLineEdit | None = None
    model: JsonTreeModel = field(default=None)
    proxy: TreeFilterProxy = field(default=None)
    name_delegate: NameDelegate = field(default=None)
    type_delegate: JsonTypeDelegate = field(default=None)
    value_delegate: ValueDelegate = field(default=None)
    _default_font_pt: int = 10
    _font_pt: int = 10
    _user_sized_columns: set[int] = field(default_factory=set)
    _programmatic_column_resize: bool = False
    _host: Any = None
    _theme: ThemeSpec | None = None
    _icon_provider: IconProvider | None = None
    _read_only: bool = False
    _monospace_fields_enabled: bool = False
    _regular_font_family: str | None = None
    _monospace_font_family: str | None = None
    _last_move_placed: list[tuple[tuple, int]] = field(default_factory=list)
    affix_mru: AffixMRU = field(default=None)
    io: Any = field(default=None)
    history: Any = field(default=None)
    mutations: DocumentMutationGateway = field(default=None)
    validation: Any = field(default=None)
    _diff_applier: Any = field(default=None)
    _editable_view_edit_triggers: Any = None
    _editable_drag_enabled: Any = None
    _editable_accept_drops: Any = None
    _editable_drag_drop_mode: Any = None

    def refresh_actions(self) -> None:
        if self._host is not None:
            self._host.refresh_actions()

    def show_permanent_message(self, message: str) -> None:
        if self._host is not None:
            self._host.show_permanent_message(message)

    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        if self._host is not None:
            self._host.show_status_message(message, timeout_ms)

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

    @property
    def schema(self) -> dict[str, Any] | None:
        return self.validation.schema if self.validation is not None else None

    @property
    def schema_ref(self) -> SchemaRef:
        return self.validation.schema_ref if self.validation is not None else None

    @property
    def schema_source(self) -> SchemaSource | None:
        return self.validation.schema_source if self.validation is not None else None

    @property
    def undo_stack(self):
        return self.history.undo_stack if self.history is not None else None

    @property
    def _move_view_state_by_cmd_id(self) -> dict:
        return self.history._move_view_state_by_cmd_id if self.history is not None else None

    @property
    def _last_undo_index(self) -> int:
        return self.history.last_undo_index if self.history is not None else 0

    @_last_undo_index.setter
    def _last_undo_index(self, value: int) -> None:
        if self.history is not None:
            self.history.last_undo_index = value

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    # ----- validation / history convenience -----------------------------

    @property
    def issue_index(self):
        return self.validation.issue_index if self.validation is not None else None

    @property
    def auto_rescan(self) -> bool:
        return self.validation.auto_rescan if self.validation is not None else False

    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]:
        return self._last_move_placed
