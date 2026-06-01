from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.validation_panel_model import IssueListModel
from documents.seams.document_protocol import Document
from state.recent_schemas import recent_schemas
from validation.index import IssueIndex
from validation.schema_registry import get_schema_registry
from validation.schema_types import SchemaRef


class ValidationDock(QDockWidget):
    issueActivated = Signal(object, bool)
    rescanRequested = Signal()
    autoRescanToggled = Signal(bool)
    clearSchemaRequested = Signal()
    # Schema picker signals — connected to MainWindow handlers
    attachSchemaRequested = Signal()
    attachRecentSchemaRequested = Signal(object)  # SchemaSource
    reloadSchemaRequested = Signal()
    openSchemaFileRequested = Signal()
    goToSchemaRuleRequested = Signal(object)  # ValidationIssue

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

        # ── toolbar ──────────────────────────────────────────────────
        self._btn_rescan = QPushButton(self.tr("🔄 Rescan now"))
        self._btn_rescan.setEnabled(False)
        self._btn_rescan.clicked.connect(self.rescanRequested)

        self._chk_auto = QCheckBox(self.tr("Auto rescan"))
        self._chk_auto.toggled.connect(self.autoRescanToggled)

        self._lbl_status = QLabel(self.tr("Up to date"))
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._btn_clear_schema = QPushButton(self.tr("🚫 Clear schema"))
        self._btn_clear_schema.setVisible(False)
        self._btn_clear_schema.clicked.connect(self.clearSchemaRequested)

        # Schema picker overflow menu button
        self._schema_btn = QToolButton(self)
        self._schema_btn.setText(self.tr("Schema ▸"))
        self._schema_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        schema_menu = QMenu(self)
        self._act_attach = schema_menu.addAction(self.tr("Attach schema…"))
        self._recent_menu = schema_menu.addMenu(self.tr("Recent"))
        self._act_reload = schema_menu.addAction(self.tr("Reload schema"))
        self._act_open = schema_menu.addAction(self.tr("Open schema file / URL"))
        self._act_attach.triggered.connect(self.attachSchemaRequested)
        self._act_reload.triggered.connect(self.reloadSchemaRequested)
        self._act_open.triggered.connect(self.openSchemaFileRequested)
        schema_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._act_reload.setEnabled(False)
        self._act_open.setEnabled(False)
        self._schema_btn.setMenu(schema_menu)
        self._rebuild_recent_menu()

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)
        toolbar_layout.addWidget(self._btn_rescan)
        toolbar_layout.addWidget(self._chk_auto)
        toolbar_layout.addWidget(self._lbl_status, 1)
        toolbar_layout.addWidget(self._schema_btn)
        toolbar_layout.addWidget(self._btn_clear_schema)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        # ─────────────────────────────────────────────────────────────

        self.model = IssueListModel(self)
        self.list_view = QListView(self)
        self.list_view.setModel(self.model)
        self.list_view.clicked.connect(self._on_index_clicked)
        self.list_view.activated.connect(self._on_index_activated)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self._on_context_menu)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(toolbar_widget)
        layout.addWidget(self.list_view)
        self.setWidget(container)

        self._tab: Document | None = None

    # ── public API ────────────────────────────────────────────────────────

    def set_auto_rescan_checked(self, enabled: bool) -> None:
        """Update the checkbox state without emitting ``autoRescanToggled``."""
        self._chk_auto.blockSignals(True)
        self._chk_auto.setChecked(enabled)
        self._chk_auto.blockSignals(False)

    def update_status(self, issue_index: IssueIndex) -> None:
        """Refresh the status label from *issue_index*."""
        issues = issue_index.all_issues()
        count = len(issues)
        if count == 0:
            self._lbl_status.setText(self.tr("Up to date"))
        else:
            self._lbl_status.setText(f"{count} issue{'s' if count != 1 else ''}")

    def attach_tab(self, tab: Document | None) -> None:
        if self._tab is tab:
            return
        if self._tab is not None:
            # Disconnect (signal, slot) pairs explicitly — no name-based reflection.
            for signal, slot in (
                (self._tab.validationChanged, self._on_validation_changed),
                (self._tab.schemaChanged, self._on_schema_changed),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            # Disconnect tree selection sync
            try:
                sm = self._tab.view.selectionModel()
                if sm is not None:
                    sm.currentChanged.disconnect(self._on_tree_selection_changed)
            except (RuntimeError, TypeError):
                pass

        self._tab = tab
        self.model.set_tab(tab)

        if tab is None:
            self.model.set_issues([])
            self._btn_rescan.setEnabled(False)
            self._btn_clear_schema.setVisible(False)
            self._lbl_status.setText(self.tr("Up to date"))
            self._act_reload.setEnabled(False)
            self._act_open.setEnabled(False)
            return

        tab.validationChanged.connect(self._on_validation_changed)
        tab.schemaChanged.connect(self._on_schema_changed)
        self._on_schema_changed(tab.validation.schema_ref)
        self._on_validation_changed(tab.validation.issue_index)

        # Sync tree selection → dock highlight
        sm = tab.view.selectionModel()
        if sm is not None:
            sm.currentChanged.connect(self._on_tree_selection_changed)

    # ── private slots ─────────────────────────────────────────────────────

    def _on_validation_changed(self, issue_index: IssueIndex) -> None:
        self.model.set_issues(issue_index.all_issues())
        self.update_status(issue_index)

    def _on_schema_changed(self, ref: SchemaRef) -> None:
        has_schema = ref.origin != "none"
        has_path = ref.path is not None
        has_url = ref.url is not None
        self._btn_rescan.setEnabled(has_schema)
        self._btn_clear_schema.setVisible(ref.origin in ("inline", "sibling", "manual"))
        self._act_reload.setEnabled(has_path or has_url)
        self._act_open.setEnabled(has_path or has_url)
        self._schema_btn.setToolTip(self.tr("URL schema - read-only") if has_url else "")

    def _on_index_clicked(self, index) -> None:
        issue = self.model.issue_at(index.row())
        if issue is not None:
            self.issueActivated.emit(issue, False)

    def _on_index_activated(self, index) -> None:
        issue = self.model.issue_at(index.row())
        if issue is not None:
            self.issueActivated.emit(issue, True)

    def _on_tree_selection_changed(self, current, previous) -> None:
        """Highlight the dock issue that corresponds to the selected tree item."""
        row = self.model.find_row_for_view_index(current)
        if row is None:
            self.list_view.clearSelection()
            return
        model_index = self.model.index(row, 0)
        self.list_view.setCurrentIndex(model_index)
        self.list_view.scrollTo(model_index)

    def _on_context_menu(self, pos) -> None:
        index = self.list_view.indexAt(pos)
        if not index.isValid():
            return
        issue = self.model.issue_at(index.row())
        if issue is None:
            return
        menu = QMenu(self)
        act_schema = menu.addAction(self.tr("Go to schema rule"))
        has_schema = self._tab is not None and (
            self._tab.validation.schema_ref.path is not None or self._tab.validation.schema_ref.url is not None
        )
        act_schema.setEnabled(has_schema and bool(issue.schema_path))
        chosen = menu.exec(self.list_view.viewport().mapToGlobal(QPoint(pos)))
        if chosen is act_schema:
            self.goToSchemaRuleRequested.emit(issue)

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        recents = recent_schemas()[:8]
        if not recents:
            act_empty = self._recent_menu.addAction(self.tr("<empty>"))
            act_empty.setEnabled(False)
            return

        for source in recents:
            if source.kind == "file":
                text = self.tr("📂 {name}").format(name=source.display)
                enabled = get_schema_registry().exists(source)
            else:
                text = self.tr("🌐 {name}").format(name=source.display)
                enabled = True
            action = self._recent_menu.addAction(text)
            action.setEnabled(enabled)
            action.triggered.connect(lambda _checked=False, s=source: self.attachRecentSchemaRequested.emit(s))
