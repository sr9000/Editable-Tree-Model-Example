from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
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

if TYPE_CHECKING:
    from documents.tab import JsonTab
    from validation.index import IssueIndex
    from validation.schema_source import SchemaRef


class ValidationDock(QDockWidget):
    issueActivated = Signal(object, bool)
    rescanRequested = Signal()
    autoRescanToggled = Signal(bool)
    clearSchemaRequested = Signal()
    # Schema picker signals — connected to MainWindow handlers
    attachSchemaRequested = Signal()
    reloadSchemaRequested = Signal()
    openSchemaFileRequested = Signal()

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
        self._act_reload = schema_menu.addAction(self.tr("Reload schema"))
        self._act_open = schema_menu.addAction(self.tr("Open schema file"))
        self._act_attach.triggered.connect(self.attachSchemaRequested)
        self._act_reload.triggered.connect(self.reloadSchemaRequested)
        self._act_open.triggered.connect(self.openSchemaFileRequested)
        self._act_reload.setEnabled(False)
        self._act_open.setEnabled(False)
        self._schema_btn.setMenu(schema_menu)

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

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(toolbar_widget)
        layout.addWidget(self.list_view)
        self.setWidget(container)

        self._tab: JsonTab | None = None

    # ── public API ────────────────────────────────────────────────────────

    def set_auto_rescan_checked(self, enabled: bool) -> None:
        """Update the checkbox state without emitting ``autoRescanToggled``."""
        self._chk_auto.blockSignals(True)
        self._chk_auto.setChecked(enabled)
        self._chk_auto.blockSignals(False)

    def update_status(self, issue_index: "IssueIndex") -> None:
        """Refresh the status label from *issue_index*."""
        issues = issue_index.all_issues()
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        if errors == 0 and warnings == 0:
            self._lbl_status.setText(self.tr("Up to date"))
        else:
            parts: list[str] = []
            if errors:
                parts.append(f"{errors} error{'s' if errors != 1 else ''}")
            if warnings:
                parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
            self._lbl_status.setText(" · ".join(parts))

    def attach_tab(self, tab: "JsonTab | None") -> None:
        if self._tab is tab:
            return
        if self._tab is not None:
            for sig_name in ("validationChanged", "schemaChanged"):
                try:
                    getattr(self._tab, sig_name).disconnect(
                        getattr(self, f"_on_{sig_name.replace('Changed', '_changed')}")
                    )
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
        self._on_schema_changed(tab.schema_ref)
        self._on_validation_changed(tab.issue_index)

    # ── private slots ─────────────────────────────────────────────────────

    def _on_validation_changed(self, issue_index: "IssueIndex") -> None:
        self.model.set_issues(issue_index.all_issues())
        self.update_status(issue_index)

    def _on_schema_changed(self, ref: "SchemaRef") -> None:
        has_schema = ref.origin != "none"
        has_path = ref.path is not None
        self._btn_rescan.setEnabled(has_schema)
        self._btn_clear_schema.setVisible(ref.origin in ("inline", "sibling", "manual"))
        self._act_reload.setEnabled(has_path)
        self._act_open.setEnabled(has_path)

    def _on_index_clicked(self, index) -> None:
        issue = self.model.issue_at(index.row())
        if issue is not None:
            self.issueActivated.emit(issue, False)

    def _on_index_activated(self, index) -> None:
        issue = self.model.issue_at(index.row())
        if issue is not None:
            self.issueActivated.emit(issue, True)
