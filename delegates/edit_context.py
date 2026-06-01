"""Edit context protocol used by editing delegates.

Decouples delegates (`ValueDelegate`, `NameDelegate`, `JsonTypeDelegate`) from
the parent widget tree. Instead of walking the parent chain to find a host
``JsonTab`` and call its private API, delegates are given a
``DelegateEditContext`` explicitly. Production code wires this context from
``documents/tab_setup.py``; tests can use ``DefaultEditContext`` to drive a
delegate against a bare ``QAbstractItemModel`` with no JsonTab in scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from PySide6.QtCore import (QAbstractItemModel, QModelIndex,
                            QPersistentModelIndex, Qt)
from PySide6.QtWidgets import QMessageBox, QWidget

from state.edit_limits import (get_binary_edit_warning_limit_bytes,
                               get_multiline_edit_warning_limit_chars,
                               get_string_edit_warning_limit_chars)
from units import counts, format_bytes


@dataclass(frozen=True)
class EditResult:
    """Outcome of a delegate-initiated commit.

    ``accepted`` mirrors the historical ``bool`` return of
    ``JsonTab.commit_set_data``. ``reopen_value_editor`` replaces the private
    ``JsonTypeDelegate._interactive`` backchannel: when a type change wants the
    host to reopen the value editor, the delegate sets this flag on its
    locally-stored "last result" and the host queries it explicitly.
    """

    accepted: bool
    reopen_value_editor: bool = False

    def __bool__(self) -> bool:  # for ergonomic ``if ctx.commit(...):`` checks
        return self.accepted


@runtime_checkable
class DelegateEditContext(Protocol):
    """Collaborators that a delegate needs from its host document."""

    def commit(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> EditResult: ...

    def notify_status(self, message: str, timeout_ms: int = 0) -> None: ...

    def icon_provider(self) -> Any | None: ...

    def affix_mru(self) -> Any | None: ...

    def confirm_large_text_edit(
        self,
        parent: QWidget | None,
        *,
        text_len: int,
        limit: int,
        title: str,
        kind: str,
    ) -> bool: ...

    def confirm_large_binary_edit(self, parent: QWidget | None, payload_size: int) -> bool: ...


def _to_index(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
    if isinstance(index, QPersistentModelIndex):
        return QModelIndex(index)
    return index


class DefaultEditContext:
    """Standalone fallback used outside of ``JsonTab``.

    Routes commits directly to ``model.setData`` and renders confirmation
    dialogs via ``QMessageBox`` using the configured edit-limit thresholds.
    ``notify_status``, ``icon_provider`` and ``affix_mru`` are no-ops / return
    ``None`` so delegates degrade gracefully in headless or third-party uses.
    """

    def __init__(
        self,
        *,
        status_sink: Optional[Callable[[str, int], None]] = None,
        affix_mru: Any | None = None,
        icon_provider: Any | None = None,
    ) -> None:
        self._status_sink = status_sink
        self._affix_mru = affix_mru
        self._icon_provider = icon_provider

    # ----- DelegateEditContext protocol -----
    def commit(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> EditResult:
        idx = _to_index(index)
        model: QAbstractItemModel | None = idx.model()
        if model is None:
            return EditResult(accepted=False)
        return EditResult(accepted=bool(model.setData(idx, value, role)))

    def notify_status(self, message: str, timeout_ms: int = 0) -> None:
        sink = self._status_sink
        if sink is None:
            return
        try:
            sink(message, timeout_ms)
        except Exception:  # pragma: no cover - defensive
            pass

    def icon_provider(self) -> Any | None:
        return self._icon_provider

    def affix_mru(self) -> Any | None:
        return self._affix_mru

    def confirm_large_text_edit(
        self,
        parent: QWidget | None,
        *,
        text_len: int,
        limit: int,
        title: str,
        kind: str,
    ) -> bool:
        if text_len <= limit:
            return True
        answer = QMessageBox.warning(
            parent,
            title,
            f"{kind} is {counts(text_len)} chars!\nLimit is {counts(limit)}.\nContinue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def confirm_large_binary_edit(self, parent: QWidget | None, payload_size: int) -> bool:
        limit = get_binary_edit_warning_limit_bytes()
        if payload_size <= limit:
            return True
        answer = QMessageBox.warning(
            parent,
            "Large binary value",
            f"Binary value is {format_bytes(payload_size)}!\n" f"Limit is {format_bytes(limit)}.\nContinue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


# Re-export the edit-limit helpers so callers building custom contexts have a
# single import path; this is convenience only.
__all__ = [
    "DefaultEditContext",
    "DelegateEditContext",
    "EditResult",
    "get_binary_edit_warning_limit_bytes",
    "get_multiline_edit_warning_limit_chars",
    "get_string_edit_warning_limit_chars",
]
