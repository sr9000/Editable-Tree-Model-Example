from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from PySide6.QtGui import QUndoStack

from documents.states.io_state import IoState
from documents.tab_dependencies import JsonTabHost
from documents.tab_history import TabHistoryController
from documents.tab_validation import TabValidationController
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
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
class JsonTabDataFacade:
    """Compatibility façade for controller-backed ``JsonTabData`` fields.

    ``JsonTabData`` is intentionally still the stable object tests and the
    application inspect directly.  This base class keeps delegating accessors
    out of the dataclass field inventory so state storage and controller/host
    forwarding can evolve independently.
    """

    _host: JsonTabHost | None = None
    io: IoState | None = None
    validation: TabValidationController | None = None
    editability: EditabilityFacadeProtocol | None = None
    appearance: AppearanceFacadeProtocol | None = None

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
    def schema_ref(self) -> SchemaRef | None:
        return self.validation.schema_ref if self.validation is not None else None

    @property
    def schema_source(self) -> SchemaSource | None:
        return self.validation.schema_source if self.validation is not None else None

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

    @property
    def issue_index(self) -> IssueIndex | None:
        return self.validation.issue_index if self.validation is not None else None

    @property
    def auto_rescan(self) -> bool:
        return self.validation.auto_rescan if self.validation is not None else False

    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]:
        return self._last_move_placed
