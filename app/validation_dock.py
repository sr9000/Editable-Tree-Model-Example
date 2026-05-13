from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDockWidget, QListView, QVBoxLayout, QWidget

from app.validation_panel_model import IssueListModel

if TYPE_CHECKING:
    from documents.tab import JsonTab
    from validation.index import IssueIndex


class ValidationDock(QDockWidget):
    issueActivated = Signal(object)

    ALLOWED_AREAS = (
        Qt.DockWidgetArea.LeftDockWidgetArea
        | Qt.DockWidgetArea.BottomDockWidgetArea
        | Qt.DockWidgetArea.RightDockWidgetArea
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("validationDock")
        self.setWindowTitle(self.tr("Validation"))
        self.setAllowedAreas(self.ALLOWED_AREAS)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        self.model = IssueListModel(self)
        self.list_view = QListView(self)
        self.list_view.setModel(self.model)
        self.list_view.clicked.connect(self._on_index_clicked)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.toolbar_placeholder = QWidget(container)
        self.toolbar_placeholder.setObjectName("validationToolbarPlaceholder")
        self.toolbar_placeholder.setFixedHeight(1)

        layout.addWidget(self.toolbar_placeholder)
        layout.addWidget(self.list_view)
        self.setWidget(container)

        self._tab: JsonTab | None = None

    def attach_tab(self, tab: JsonTab | None) -> None:
        if self._tab is tab:
            return
        if self._tab is not None:
            try:
                self._tab.validationChanged.disconnect(self._on_validation_changed)
            except (RuntimeError, TypeError):
                pass

        self._tab = tab
        self.model.set_tab(tab)

        if tab is None:
            self.model.set_issues([])
            return

        tab.validationChanged.connect(self._on_validation_changed)
        self._on_validation_changed(tab.issue_index)

    def _on_validation_changed(self, issue_index: "IssueIndex") -> None:
        self.model.set_issues(issue_index.all_issues())

    def _on_index_clicked(self, index) -> None:
        issue = self.model.issue_at(index.row())
        if issue is not None:
            self.issueActivated.emit(issue)
