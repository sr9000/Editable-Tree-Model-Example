from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget


class ValueDelegateProtocol(Protocol):
    """Delegate-side seam the editor factory talks back to.

    Implemented by ``delegates.value.ValueDelegate``; kept here so the
    ``editors`` package never imports ``delegates`` (dependency points
    delegates -> editors, never the reverse).
    """

    _secret_watchers: dict[QWidget, QObject]

    def _context_for(self, host) -> "EditorContextProtocol": ...

    def _finalize_secret_editor(self, editor: QWidget, index: QPersistentModelIndex) -> None: ...

    def _apply_monospace_font(self, font: QFont) -> QFont: ...

    def _mark_editor_open(self, index: QModelIndex | QPersistentModelIndex) -> None: ...


class EditorContextProtocol(Protocol):
    """Host-side seam: the only way an editor reaches the application.

    Concrete editors stay context-free; the factory receives an
    implementation of this protocol so it can commit values and raise
    confirmations without importing ``app`` or ``documents``.
    """

    def commit(self, index: QModelIndex, value, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole): ...

    def notify_status(self, message: str, timeout_ms: int = 0) -> None: ...

    def confirm_large_binary_edit(self, parent, payload_size: int) -> bool: ...

    def confirm_large_text_edit(
        self,
        parent,
        *,
        text_len: int,
        limit: int,
        title: str,
        kind: str,
    ) -> bool: ...

    def affix_mru(self): ...

    def icon_provider(self): ...
