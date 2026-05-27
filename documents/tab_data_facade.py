from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtGui import QUndoStack

from documents.tab_dependencies import JsonTabHost
from documents.tab_history import TabHistoryController
from documents.tab_io_controller import TabIOController
from documents.tab_validation import TabValidationController
from validation.index import IssueIndex
from validation.schema_registry import SchemaSource
from validation.schema_source import SchemaRef


@dataclass
class JsonTabDataFacade:
    """Compatibility façade for controller-backed ``JsonTabData`` fields.

    ``JsonTabData`` is intentionally still the stable object tests and the
    application inspect directly.  This base class keeps delegating accessors
    out of the dataclass field inventory so state storage and controller/host
    forwarding can evolve independently.
    """

    _host: JsonTabHost | None = None
    io: TabIOController | None = None
    history: TabHistoryController | None = None
    validation: TabValidationController | None = None
    _read_only: bool = False
    _last_move_placed: list[tuple[tuple[int, ...], int]] = field(default_factory=list)

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
        return self._read_only

    @property
    def issue_index(self) -> IssueIndex | None:
        return self.validation.issue_index if self.validation is not None else None

    @property
    def auto_rescan(self) -> bool:
        return self.validation.auto_rescan if self.validation is not None else False

    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]:
        return self._last_move_placed
