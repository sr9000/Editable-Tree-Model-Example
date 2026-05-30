from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from validation.issue import ValidationIssue
from validation.json_pointer import instance_path_to_model_path


class ValidationPanelTabProtocol(Protocol):
    data_store: Any
    view_controller: Any

    def root_data(self) -> Any: ...


def _instance_path_to_json_path(instance_path: tuple[str | int, ...]) -> str:
    parts = ["$"]
    for segment in instance_path:
        if isinstance(segment, int):
            parts.append(f"[{segment}]")
            continue
        if segment.isidentifier():
            parts.append(f".{segment}")
        else:
            escaped = segment.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'["{escaped}"]')
    return "".join(parts)


class IssueListModel(QAbstractListModel):
    """List model used by the validation dock panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._issues: list[ValidationIssue] = []
        self._display: list[str] = []
        self._tab: ValidationPanelTabProtocol | None = None
        self._root_data: Any = None

    def set_tab(self, tab: ValidationPanelTabProtocol | None) -> None:
        self._tab = tab
        self._root_data = tab.root_data() if tab is not None else None
        self._rebuild_display_cache()

    def set_issues(self, issues: Sequence[ValidationIssue]) -> None:
        self.beginResetModel()
        if self._tab is not None:
            self._root_data = self._tab.root_data()
        self._issues = list(issues)
        self._rebuild_display_cache()
        self.endResetModel()

    def issue_at(self, row: int) -> ValidationIssue | None:
        if 0 <= row < len(self._issues):
            return self._issues[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._issues)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        row = index.row()
        if not index.isValid() or not (0 <= row < len(self._issues)):
            return None

        issue = self._issues[row]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display[row]
        if role == Qt.ItemDataRole.ToolTipRole:
            return issue.message
        return None

    def _rebuild_display_cache(self) -> None:
        self._display = [self._format_issue(issue) for issue in self._issues]

    def _format_issue(self, issue: ValidationIssue) -> str:
        path_text = self._format_issue_path(issue)
        return f"🔶 [{issue.kind}] {path_text} — {issue.message}"

    def _format_issue_path(self, issue: ValidationIssue) -> str:
        if self._tab is not None:
            model_path = instance_path_to_model_path(self._root_data, issue.instance_path)
            if model_path is not None:
                index = self._tab.view_controller.index_from_path(model_path)
                if index.isValid():
                    return self._tab.view_controller.qualified_name(index)
        return _instance_path_to_json_path(issue.instance_path)

    def find_row_for_view_index(self, view_index: "QModelIndex") -> int | None:
        """Return the first issue row whose instance_path resolves to *view_index*, or None."""
        if self._tab is None or not view_index.isValid():
            return None
        src_index = self._tab.view_controller.proxy_to_source(view_index).siblingAtColumn(0)
        for row, issue in enumerate(self._issues):
            model_path = instance_path_to_model_path(self._root_data, issue.instance_path)
            if model_path is None:
                continue
            idx = self._tab.view_controller.index_from_path(model_path)
            if not idx.isValid():
                continue
            if self._tab.view_controller.source_to_view(idx.siblingAtColumn(0)) == view_index.siblingAtColumn(0):
                return row
        return None
