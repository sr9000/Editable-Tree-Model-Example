"""Presenter for validation-dock interaction (kill-gods Phase 3.3).

Owns the on-dock-signal handlers, the schema-attach flow, the Schemas
top-level menu, and the permanent validation status label binding. The
``ValidationDock`` widget itself still lives in ``app/validation_dock.py``;
this presenter merely wires it to the rest of the app.

Public widgets/actions that other code (tests, theme controller, action
state) reaches via ``MainWindow`` are still installed onto the window so
existing references like ``window.validation_dock`` continue to work.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QLabel, QMenu

from app.validation_dock import ValidationDock
from dialogs.attach_schema_dlg import AttachSchemaDialog
from state.recent_schemas import recent_schemas
from validation.schema_registry import SchemaSource, get_schema_registry, open_in_browser


class DockValidationPresenter(QObject):
    """Wires ``ValidationDock`` and the Schemas menu to ``MainWindow``."""

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._win = main_window
        self._setup_validation_dock()
        self._setup_schemas_menu()

    # ── dock + status label ──────────────────────────────────────────────

    def _setup_validation_dock(self) -> None:
        from state.validation_settings import auto_rescan_enabled

        win = self._win
        win.validation_dock = ValidationDock(win)
        win.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, win.validation_dock)
        win.validation_dock.issueActivated.connect(
            lambda issue, edit: self.on_validation_issue_activated(issue, edit=edit)
        )
        win.validation_dock.rescanRequested.connect(self.on_rescan_requested)
        win.validation_dock.autoRescanToggled.connect(self.on_auto_rescan_toggled)
        win.validation_dock.clearSchemaRequested.connect(self.on_clear_schema_requested)
        win.validation_dock.attachSchemaRequested.connect(self.on_attach_schema_requested)
        win.validation_dock.attachRecentSchemaRequested.connect(self.on_attach_recent_schema_requested)
        win.validation_dock.reloadSchemaRequested.connect(self.on_reload_schema_requested)
        win.validation_dock.openSchemaFileRequested.connect(self.on_open_schema_file_requested)
        win.validation_dock.goToSchemaRuleRequested.connect(self.on_go_to_schema_rule_requested)

        win.validation_dock.set_auto_rescan_checked(auto_rescan_enabled())

        # Permanent right-aligned status label.
        win._validation_status_label = QLabel("", win)
        win._validation_status_label.setVisible(False)
        win.statusBar.addPermanentWidget(win._validation_status_label)
        win._bound_validation_tab = None

        win.viewValidationPanelAction = QAction(win.tr("Validation Panel"), win)
        win.viewValidationPanelAction.setCheckable(True)
        win.viewMenu.addSeparator()
        win.viewMenu.addAction(win.viewValidationPanelAction)

        dock_state = win._settings.value("validation/dock_state")
        if isinstance(dock_state, QByteArray):
            win.restoreState(dock_state)
        elif isinstance(dock_state, (bytes, bytearray)):
            win.restoreState(QByteArray(dock_state))

        visible = win._coerce_bool(win._settings.value("validation/dock_visible", True), default=True)
        win.validation_dock.setVisible(visible)
        win.viewValidationPanelAction.setChecked(visible)

    # ── tab-bound validation status label ─────────────────────────────────

    def bind_validation_status(self, tab) -> None:
        win = self._win
        if win._bound_validation_tab is not None:
            try:
                win._bound_validation_tab.validationChanged.disconnect(self.on_tab_validation_changed)
            except (RuntimeError, TypeError):
                pass
        win._bound_validation_tab = tab
        if tab is not None:
            tab.validationChanged.connect(self.on_tab_validation_changed)
            self.on_tab_validation_changed(tab.data_store.issue_index)
        else:
            win._validation_status_label.setVisible(False)

    def on_tab_validation_changed(self, issue_index) -> None:
        from documents.tab_status import format_validation_status

        win = self._win
        text = format_validation_status(issue_index)
        if text:
            win._validation_status_label.setText(text)
            win._validation_status_label.setVisible(True)
        else:
            win._validation_status_label.setVisible(False)

    # ── dock signal handlers ─────────────────────────────────────────────

    def on_validation_issue_activated(self, issue, *, edit: bool = False) -> None:
        tab = self._win._current_tab()
        if tab is None:
            return
        tab.goto_validation_issue(issue, edit=edit)

    def on_rescan_requested(self) -> None:
        tab = self._win._current_tab()
        if tab is not None:
            tab.data_store.validation.revalidate()

    def on_auto_rescan_toggled(self, enabled: bool) -> None:
        from state.validation_settings import set_auto_rescan_enabled

        set_auto_rescan_enabled(enabled)
        for tab in self._win._theme_tabs():
            tab.data_store.validation.set_auto_rescan(enabled)

    def on_clear_schema_requested(self) -> None:
        from state.validation_settings import clear_schema_path

        tab = self._win._current_tab()
        if tab is None:
            return
        if tab.data_store.file_path:
            clear_schema_path(Path(tab.data_store.file_path))
        tab.data_store.validation.clear_schema()

    def on_attach_schema_requested(self) -> None:
        win = self._win
        tab = win._current_tab()
        if tab is None:
            return
        source = AttachSchemaDialog.ask(win, start_dir=tab.data_store.file_path or "")
        if source is None:
            return
        self.attach_schema_source(source)

    def on_attach_recent_schema_requested(self, source: SchemaSource) -> None:
        self.attach_schema_source(source)

    def attach_schema_source(self, source: SchemaSource) -> None:
        from state.validation_settings import write_schema_ref_str

        win = self._win
        tab = win._current_tab()
        if tab is None:
            return

        entry = get_schema_registry().acquire(source, tab)
        if entry is None:
            win.statusBar.showMessage(win.tr("Could not load schema: {name}").format(name=source.display), 3000)
            return

        tab.data_store.validation.set_schema_from_source(source)
        if tab.data_store.file_path:
            write_schema_ref_str(Path(tab.data_store.file_path), source.key)
        win.statusBar.showMessage(win.tr("Schema attached: {name}").format(name=source.display), 2000)

    def on_reload_schema_requested(self) -> None:
        win = self._win
        tab = win._current_tab()
        if tab is None or tab.data_store.schema_source is None:
            return
        if get_schema_registry().reload(tab.data_store.schema_source) is None:
            win.statusBar.showMessage(win.tr("Reload failed"), 3000)
            return
        tab.data_store.validation.revalidate()
        win.statusBar.showMessage(win.tr("Schema reloaded"), 2000)

    def on_open_schema_file_requested(self) -> None:
        win = self._win
        tab = win._current_tab()
        if tab is None or tab.data_store.schema_source is None:
            return

        source = tab.data_store.schema_source
        if source is None:
            return
        if source.kind == "url":
            if not open_in_browser(source):
                win.statusBar.showMessage(win.tr("Could not open schema URL"), 3000)
            return

        path = source.key
        if not os.path.exists(path):
            win.statusBar.showMessage(win.tr("Schema file not found"), 3000)
            return
        win._open_path(path)

    def on_go_to_schema_rule_requested(self, issue) -> None:
        """Open the schema and navigate to the rule that triggered *issue*."""
        win = self._win
        tab = win._current_tab()
        if tab is None:
            return

        from validation.issue import ValidationIssue

        def _navigate(schema_tab):
            if schema_tab is None or not issue.schema_path:
                return
            fake_issue = ValidationIssue(
                message="",
                instance_path=issue.schema_path,
                schema_path=(),
                kind="",
            )
            schema_tab.goto_validation_issue(fake_issue)

        source = tab.data_store.schema_source
        if source is None:
            return
        schema_tab = win._schema_tab_pool.open_or_focus(win, source)
        if schema_tab is None:
            if source.kind == "file":
                win.statusBar.showMessage(win.tr("Schema file not found"), 3000)
            else:
                win.statusBar.showMessage(win.tr("Could not fetch schema for navigation"), 3000)
            return
        _navigate(schema_tab)

    # ── Schemas top-level menu ───────────────────────────────────────────

    def _setup_schemas_menu(self) -> None:
        win = self._win
        win.schemasMenu = QMenu(win.tr("Schemas"), win)
        win.menuBar.insertMenu(win.viewMenu.menuAction(), win.schemasMenu)

        win._schemas_attach_action = QAction(win.tr("Attach schema…"), win)
        win._schemas_attach_action.triggered.connect(self.on_attach_schema_requested)
        win._schemas_recent_menu = QMenu(win.tr("Recent"), win)
        win._schemas_open_current_action = QAction(win.tr("Open current schema"), win)
        win._schemas_open_current_action.triggered.connect(
            lambda: (
                self.open_schema_source(win._current_tab().data_store.schema_source)
                if win._current_tab() is not None
                else None
            )
        )
        win._schemas_copy_path_action = QAction(win.tr("Copy full path"), win)
        win._schemas_copy_path_action.triggered.connect(
            lambda: (
                self.copy_schema_source_key(win._current_tab().data_store.schema_source)
                if win._current_tab() is not None
                else None
            )
        )

        win.schemasMenu.aboutToShow.connect(self.rebuild_schemas_menu)

    def open_schema_source(self, source: SchemaSource | None) -> None:
        win = self._win
        if source is None:
            return
        tab = win._schema_tab_pool.open_or_focus(win, source)
        if tab is None:
            if source.kind == "file":
                win.statusBar.showMessage(win.tr("Schema file not found"), 3000)
            else:
                win.statusBar.showMessage(win.tr("Could not open schema URL"), 3000)

    def copy_schema_source_key(self, source: SchemaSource | None) -> None:
        win = self._win
        if source is None:
            return
        QApplication.clipboard().setText(source.key)
        win.statusBar.showMessage(win.tr("Copied schema path"), 1500)

    def rebuild_schemas_menu(self) -> None:
        win = self._win
        win.schemasMenu.clear()
        win.schemasMenu.addAction(win._schemas_attach_action)
        win.schemasMenu.addMenu(win._schemas_recent_menu)
        win.schemasMenu.addSeparator()
        win.schemasMenu.addAction(win._schemas_open_current_action)
        win.schemasMenu.addAction(win._schemas_copy_path_action)

        win._schemas_recent_menu.clear()
        for source in recent_schemas()[:8]:
            label = (
                win.tr("📂 {name}").format(name=source.display)
                if source.kind == "file"
                else win.tr("🌐 {name}").format(name=source.display)
            )
            action = win._schemas_recent_menu.addAction(label)
            if source.kind == "file":
                action.setEnabled(Path(source.key).exists())
            action.triggered.connect(lambda _checked=False, s=source: self.open_schema_source(s))

        if not win._schemas_recent_menu.actions():
            empty = win._schemas_recent_menu.addAction(win.tr("<empty>"))
            empty.setEnabled(False)

        tab = win._current_tab()
        source = tab.data_store.schema_source if tab is not None else None
        has_source = source is not None
        win._schemas_open_current_action.setEnabled(has_source)
        win._schemas_copy_path_action.setEnabled(has_source)
