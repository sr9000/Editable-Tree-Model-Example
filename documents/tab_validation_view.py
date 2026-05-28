from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView

from documents.tab_protocols import TabValidationViewProtocol
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.json_pointer import instance_path_to_model_path

_SELECT_ROW_FLAGS = QItemSelectionModel.SelectionFlag(
    QItemSelectionModel.SelectionFlag.ClearAndSelect.value | QItemSelectionModel.SelectionFlag.Rows.value
)
_EDITABLE_ITEM_FLAG = Qt.ItemFlag.ItemIsEditable.value


class JsonTabValidationViewController:
    """Own validation issue navigation and validation repaint behavior."""

    def __init__(self, tab: TabValidationViewProtocol) -> None:
        self._tab = tab

    def goto_validation_issue(self, issue: ValidationIssue, *, edit: bool = False) -> bool:
        root_data = self._tab.data_store.model.root_item.to_json()
        model_path = instance_path_to_model_path(root_data, issue.instance_path)
        if model_path is None:
            self._tab.show_status("Validation issue path no longer exists", 2000)
            return False

        source_row = self._tab._index_from_path(model_path)
        if not source_row.isValid():
            self._tab.show_status("Validation issue path no longer exists", 2000)
            return False

        source_row = source_row.siblingAtColumn(0)
        view_row = self._tab._source_to_view(source_row)
        if not view_row.isValid():
            self._tab.show_status("Validation issue path no longer exists", 2000)
            return False

        selection_model = self._tab.data_store.view.selectionModel()
        if selection_model is not None:
            selection_model.select(view_row, _SELECT_ROW_FLAGS)
            selection_model.setCurrentIndex(view_row, QItemSelectionModel.SelectionFlag.NoUpdate)

        view = self._tab.data_store.view
        view.setCurrentIndex(view_row)
        view.scrollTo(view_row, QAbstractItemView.ScrollHint.PositionAtCenter)

        if not edit:
            return True

        source_value = source_row.siblingAtColumn(2)
        if not source_value.isValid():
            return True
        if not (self._tab.data_store.model.flags(source_value).value & _EDITABLE_ITEM_FLAG):
            return True

        view_value = self._tab._source_to_view(source_value)
        if not view_value.isValid():
            return True
        view.setCurrentIndex(view_value)
        view.edit(view_value)
        return True

    def severity_provider(self, model_path: tuple[int, ...]) -> str | None:
        return self._tab.data_store.validation.severity_for(model_path)

    def on_validation_changed(self, _index: IssueIndex) -> None:
        """Emit recursive dataChanged so all visible rows repaint their badges."""

        def emit_ranges(parent: QModelIndex) -> None:
            model = self._tab.data_store.model
            rows = model.rowCount(parent)
            if rows <= 0:
                return
            top_left = model.index(0, 0, parent)
            bottom_right = model.index(rows - 1, model.columnCount(parent) - 1, parent)
            model.dataChanged.emit(top_left, bottom_right, [VALIDATION_SEVERITY_ROLE])
            for row in range(rows):
                emit_ranges(model.index(row, 0, parent))

        emit_ranges(QModelIndex())


__all__ = ["JsonTabValidationViewController"]
