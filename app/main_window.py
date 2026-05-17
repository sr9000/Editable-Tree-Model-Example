# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QModelIndex, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFontDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTreeView,
    QUndoView,
)

import state.view_state as view_state
from app.close_confirm import confirm_close
from app.font_controller import FontController
from app.history import bind_undo_signals, setup_history_menu
from app.main_window_actions import setup_connections as setup_main_window_connections
from app.main_window_actions import update_actions as update_main_window_actions
from app.recent_files import push_recent, refresh_recent_menu
from app.schema_tab_pool import SchemaTabPool
from app.theme_controller import ThemeController
from app.validation_dock import ValidationDock
from dialogs.attach_schema_dlg import AttachSchemaDialog
from documents.tab import JsonTab
from io_formats.load import load_file_with_format
from mainwindow import Ui_MainWindow
from settings import APPLICATION_ID, WINDOW_DEFAULT_SIZE
from state.edit_limits import (
    get_attach_file_warning_limit_bytes,
    get_binary_edit_warning_limit_bytes,
    get_multiline_edit_warning_limit_chars,
    get_string_edit_warning_limit_chars,
    set_attach_file_warning_limit_bytes,
    set_binary_edit_warning_limit_bytes,
    set_multiline_edit_warning_limit_chars,
    set_string_edit_warning_limit_chars,
)
from state.recent_schemas import recent_schemas
from tree_actions.clipboard import copy_selection
from tree_actions.structure import collapse_all, delete_selection, expand_all
from units import counts, format_bytes
from validation.schema_registry import SchemaSource, open_in_browser, schema_registry


class MainWindow(QMainWindow, Ui_MainWindow):
    @staticmethod
    def _coerce_bool(value, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().casefold()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return default

    @staticmethod
    def _normalize_font_for_dialog(seed: QFont) -> QFont:
        font = QFont(seed)
        if font.pointSizeF() <= 0:
            font.setPointSize(10)
        return font

    @staticmethod
    def _unpack_font_dialog_result(result) -> tuple[QFont | None, bool]:
        # PySide can expose getFont() tuple order as (QFont, bool) or (bool, QFont)
        # depending on binding/runtime details.
        if isinstance(result, tuple) and len(result) == 2:
            first, second = result
            if isinstance(first, QFont) and isinstance(second, bool):
                return first, second
            if isinstance(first, bool) and isinstance(second, QFont):
                return second, first
        return None, False

    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setAcceptDrops(True)
        self._history_dialog: QDialog | None = None
        self._history_view: QUndoView | None = None
        self._bound_undo_tab: JsonTab | None = None
        self._startup_window_mode: str = "normal"
        self._settings = QSettings(APPLICATION_ID, "app")
        # All font preferences (regular family, monospace family, editor
        # point size, monospace-fields toggle) live in a single controller
        # that persists itself and broadcasts to subscribed tabs. See
        # ``app/font_controller.py``.
        self.fonts = FontController(self._settings, self)
        self._theme_controller = ThemeController(self, self._on_theme_applied)
        self._theme_registry = self._theme_controller.registry
        self._theme = self._theme_controller.theme
        self._icon_provider = self._theme_controller.icon_provider
        self._schema_tab_pool = SchemaTabPool(self)
        self._theme_follow_action = self._theme_controller.follow_action
        self._recent_menu = QMenu("Recent", self)
        self.fileMenu.insertMenu(self.appExitAction, self._recent_menu)
        self.fileMenu.insertSeparator(self.appExitAction)
        self._setup_edit_limits_menu()
        refresh_recent_menu(self)
        self._setup_schemas_menu()
        self._setup_validation_dock()
        self._setup_font_actions()
        self._setup_monospace_action()
        setup_history_menu(self)
        self.setup_model(yaml_filename)
        self.setup_connections()
        self._restore_window_geometry()

    def _restore_window_geometry(self) -> None:
        geometry = self._settings.value("window/geometry")
        restored = False
        if isinstance(geometry, QByteArray):
            restored = self.restoreGeometry(geometry)
        elif isinstance(geometry, (bytes, bytearray)):
            restored = self.restoreGeometry(QByteArray(bytes(geometry)))

        if not restored:
            self.resize(*WINDOW_DEFAULT_SIZE)

        if self._coerce_bool(self._settings.value("window/fullscreen", False), default=False):
            self._startup_window_mode = "fullscreen"
            return

        if self._coerce_bool(self._settings.value("window/maximized", False), default=False):
            self._startup_window_mode = "maximized"
            return

        self._startup_window_mode = "normal"

    def show_with_restored_mode(self) -> None:
        self.show()

        if self._startup_window_mode == "fullscreen":
            QTimer.singleShot(100, self.showFullScreen)
            return

        if self._startup_window_mode == "maximized":
            QTimer.singleShot(100, self.showMaximized)
            return

    @staticmethod
    def _local_paths_from_mime(mime: QMimeData) -> list[str]:
        """Return deduplicated absolute local file paths from a MIME payload."""
        paths: list[str] = []
        seen: set[str] = set()
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            resolved = str(Path(url.toLocalFile()).resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(resolved)
        return paths

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self._local_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = self._local_paths_from_mime(event.mimeData())
        if not paths:
            event.ignore()
            return

        opened_any = False
        for path in paths:
            opened_any = self._open_path(path) or opened_any

        if opened_any:
            event.acceptProposedAction()
            return
        event.ignore()

    def _setup_validation_dock(self) -> None:
        from state.validation_settings import auto_rescan_enabled

        self.validation_dock = ValidationDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.validation_dock)
        self.validation_dock.issueActivated.connect(
            lambda issue, edit: self._on_validation_issue_activated(issue, edit=edit)
        )
        self.validation_dock.rescanRequested.connect(self._on_rescan_requested)
        self.validation_dock.autoRescanToggled.connect(self._on_auto_rescan_toggled)
        self.validation_dock.clearSchemaRequested.connect(self._on_clear_schema_requested)
        self.validation_dock.attachSchemaRequested.connect(self._on_attach_schema_requested)
        self.validation_dock.attachRecentSchemaRequested.connect(self._on_attach_recent_schema_requested)
        self.validation_dock.reloadSchemaRequested.connect(self._on_reload_schema_requested)
        self.validation_dock.openSchemaFileRequested.connect(self._on_open_schema_file_requested)
        self.validation_dock.goToSchemaRuleRequested.connect(self._on_go_to_schema_rule_requested)

        # Initialise checkbox from the persisted global setting.
        self.validation_dock.set_auto_rescan_checked(auto_rescan_enabled())

        # Permanent right-aligned label on the status bar for validation summary.
        self._validation_status_label = QLabel("", self)
        self._validation_status_label.setVisible(False)
        self.statusBar.addPermanentWidget(self._validation_status_label)
        self._bound_validation_tab = None

        self.viewValidationPanelAction = QAction(self.tr("Validation Panel"), self)
        self.viewValidationPanelAction.setCheckable(True)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.viewValidationPanelAction)

        dock_state = self._settings.value("validation/dock_state")
        if isinstance(dock_state, QByteArray):
            self.restoreState(dock_state)
        elif isinstance(dock_state, (bytes, bytearray)):
            self.restoreState(QByteArray(dock_state))

        visible = self._coerce_bool(self._settings.value("validation/dock_visible", True), default=True)
        self.validation_dock.setVisible(visible)
        self.viewValidationPanelAction.setChecked(visible)

    # ── validation dock handlers ──────────────────────────────────────────

    def _on_rescan_requested(self) -> None:
        tab = self._current_tab()
        if tab is not None:
            tab.revalidate()

    def _on_auto_rescan_toggled(self, enabled: bool) -> None:
        from state.validation_settings import set_auto_rescan_enabled

        set_auto_rescan_enabled(enabled)
        for tab in self._theme_tabs():
            tab.set_auto_rescan(enabled)

    def _on_clear_schema_requested(self) -> None:
        from state.validation_settings import clear_schema_path

        tab = self._current_tab()
        if tab is None:
            return
        if tab.file_path:
            clear_schema_path(Path(tab.file_path))
        tab.clear_schema()

    def _on_attach_schema_requested(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        source = AttachSchemaDialog.ask(self, start_dir=tab.file_path or "")
        if source is None:
            return

        self._attach_schema_source(source)

    def _on_attach_recent_schema_requested(self, source: SchemaSource) -> None:
        self._attach_schema_source(source)

    def _attach_schema_source(self, source: SchemaSource) -> None:
        from state.validation_settings import write_schema_ref_str

        tab = self._current_tab()
        if tab is None:
            return

        entry = schema_registry.acquire(source, tab)
        if entry is None:
            self.statusBar.showMessage(self.tr("Could not load schema: {name}").format(name=source.display), 3000)
            return

        tab.set_schema_from_source(source)
        if tab.file_path:
            write_schema_ref_str(Path(tab.file_path), source.key)
        self.statusBar.showMessage(self.tr("Schema attached: {name}").format(name=source.display), 2000)

    def _on_reload_schema_requested(self) -> None:
        tab = self._current_tab()
        if tab is None or tab.schema_source is None:
            return
        if schema_registry.reload(tab.schema_source) is None:
            self.statusBar.showMessage(self.tr("Reload failed"), 3000)
            return
        tab.revalidate()
        self.statusBar.showMessage(self.tr("Schema reloaded"), 2000)

    def _on_open_schema_file_requested(self) -> None:
        tab = self._current_tab()
        if tab is None or tab.schema_source is None:
            return

        source = tab.schema_source
        if source is None:
            return
        if source.kind == "url":
            if not open_in_browser(source):
                self.statusBar.showMessage(self.tr("Could not open schema URL"), 3000)
            return

        path = source.key
        import os

        if not os.path.exists(path):
            self.statusBar.showMessage(self.tr("Schema file not found"), 3000)
            return
        self._open_path(path)

    def _on_go_to_schema_rule_requested(self, issue) -> None:
        """Open the schema and navigate to the rule that triggered *issue*."""
        tab = self._current_tab()
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

        source = tab.schema_source
        if source is None:
            return
        schema_tab = self._schema_tab_pool.open_or_focus(self, source)
        if schema_tab is None:
            if source.kind == "file":
                self.statusBar.showMessage(self.tr("Schema file not found"), 3000)
            else:
                self.statusBar.showMessage(self.tr("Could not fetch schema for navigation"), 3000)
            return
        _navigate(schema_tab)

    def _setup_schemas_menu(self) -> None:
        self.schemasMenu = QMenu(self.tr("Schemas"), self)
        self.menuBar.insertMenu(self.viewMenu.menuAction(), self.schemasMenu)

        self._schemas_attach_action = QAction(self.tr("Attach schema…"), self)
        self._schemas_attach_action.triggered.connect(self._on_attach_schema_requested)
        self._schemas_recent_menu = QMenu(self.tr("Recent"), self)
        self._schemas_open_current_action = QAction(self.tr("Open current schema"), self)
        self._schemas_open_current_action.triggered.connect(
            lambda: (
                self._open_schema_source(self._current_tab().schema_source) if self._current_tab() is not None else None
            )
        )
        self._schemas_copy_path_action = QAction(self.tr("Copy full path"), self)
        self._schemas_copy_path_action.triggered.connect(
            lambda: (
                self._copy_schema_source_key(self._current_tab().schema_source)
                if self._current_tab() is not None
                else None
            )
        )

        self.schemasMenu.aboutToShow.connect(self._rebuild_schemas_menu)

    def _open_schema_source(self, source: SchemaSource | None) -> None:
        if source is None:
            return
        tab = self._schema_tab_pool.open_or_focus(self, source)
        if tab is None:
            if source.kind == "file":
                self.statusBar.showMessage(self.tr("Schema file not found"), 3000)
            else:
                self.statusBar.showMessage(self.tr("Could not open schema URL"), 3000)

    def _copy_schema_source_key(self, source: SchemaSource | None) -> None:
        if source is None:
            return
        QApplication.clipboard().setText(source.key)
        self.statusBar.showMessage(self.tr("Copied schema path"), 1500)

    def _rebuild_schemas_menu(self) -> None:
        self.schemasMenu.clear()
        self.schemasMenu.addAction(self._schemas_attach_action)
        self.schemasMenu.addMenu(self._schemas_recent_menu)
        self.schemasMenu.addSeparator()
        self.schemasMenu.addAction(self._schemas_open_current_action)
        self.schemasMenu.addAction(self._schemas_copy_path_action)

        self._schemas_recent_menu.clear()
        for source in recent_schemas()[:8]:
            label = (
                self.tr("📂 {name}").format(name=source.display)
                if source.kind == "file"
                else self.tr("🌐 {name}").format(name=source.display)
            )
            action = self._schemas_recent_menu.addAction(label)
            if source.kind == "file":
                action.setEnabled(Path(source.key).exists())
            action.triggered.connect(lambda _checked=False, s=source: self._open_schema_source(s))

        if not self._schemas_recent_menu.actions():
            empty = self._schemas_recent_menu.addAction(self.tr("<empty>"))
            empty.setEnabled(False)

        tab = self._current_tab()
        source = tab.schema_source if tab is not None else None
        has_source = source is not None
        self._schemas_open_current_action.setEnabled(has_source)
        self._schemas_copy_path_action.setEnabled(has_source)

    def _setup_edit_limits_menu(self) -> None:
        self._limits_menu = QMenu(self.tr("Edit Warning Limits"), self)
        self._limit_string_action = QAction(self)
        self._limit_multiline_action = QAction(self)
        self._limit_binary_action = QAction(self)
        self._limit_attach_action = QAction(self)

        self._limit_string_action.triggered.connect(self._set_string_warning_limit)
        self._limit_multiline_action.triggered.connect(self._set_multiline_warning_limit)
        self._limit_binary_action.triggered.connect(self._set_binary_warning_limit)
        self._limit_attach_action.triggered.connect(self._set_attach_warning_limit)

        self._limits_menu.addAction(self._limit_string_action)
        self._limits_menu.addAction(self._limit_multiline_action)
        self._limits_menu.addAction(self._limit_binary_action)
        self._limits_menu.addAction(self._limit_attach_action)
        self._limits_menu.aboutToShow.connect(self._refresh_edit_limits_menu_entries)
        self._refresh_edit_limits_menu_entries()

        self.fileMenu.insertMenu(self.appExitAction, self._limits_menu)
        self.fileMenu.insertSeparator(self.appExitAction)

    def _refresh_edit_limits_menu_entries(self) -> None:
        string_limit = get_string_edit_warning_limit_chars()
        multiline_limit = get_multiline_edit_warning_limit_chars()
        binary_limit = get_binary_edit_warning_limit_bytes()
        attach_limit = get_attach_file_warning_limit_bytes()

        self._limit_string_action.setText(
            self.tr("String edit limit... ({value} chars)").format(value=counts(string_limit))
        )
        self._limit_multiline_action.setText(
            self.tr("Multiline text limit... ({value} chars)").format(value=counts(multiline_limit))
        )
        self._limit_binary_action.setText(
            self.tr("Bytes edit limit... ({value})").format(value=format_bytes(binary_limit))
        )
        self._limit_attach_action.setText(
            self.tr("Attach file size limit... ({value})").format(value=format_bytes(attach_limit))
        )

    def _prompt_limit_value(self, *, title: str, label: str, current: int) -> int | None:
        value, ok = QInputDialog.getInt(self, title, label, current, 1, 2_147_483_647, 1)
        if not ok:
            return None
        return int(value)

    def _set_string_warning_limit(self) -> None:
        current = get_string_edit_warning_limit_chars()
        value = self._prompt_limit_value(
            title=self.tr("String Edit Warning Limit"),
            label=self.tr("Warn when string length exceeds (chars):"),
            current=current,
        )
        if value is None:
            return
        set_string_edit_warning_limit_chars(value)
        self._refresh_edit_limits_menu_entries()
        self.statusBar.showMessage(self.tr("Updated string edit warning limit"), 2000)

    def _set_multiline_warning_limit(self) -> None:
        current = get_multiline_edit_warning_limit_chars()
        value = self._prompt_limit_value(
            title=self.tr("Multiline Edit Warning Limit"),
            label=self.tr("Warn when multiline length exceeds (chars):"),
            current=current,
        )
        if value is None:
            return
        set_multiline_edit_warning_limit_chars(value)
        self._refresh_edit_limits_menu_entries()
        self.statusBar.showMessage(self.tr("Updated multiline edit warning limit"), 2000)

    def _set_binary_warning_limit(self) -> None:
        current = get_binary_edit_warning_limit_bytes()
        value = self._prompt_limit_value(
            title=self.tr("Bytes Edit Warning Limit"),
            label=self.tr("Warn when binary size exceeds (bytes):"),
            current=current,
        )
        if value is None:
            return
        set_binary_edit_warning_limit_bytes(value)
        self._refresh_edit_limits_menu_entries()
        self.statusBar.showMessage(self.tr("Updated bytes edit warning limit"), 2000)

    def _set_attach_warning_limit(self) -> None:
        current = get_attach_file_warning_limit_bytes()
        value = self._prompt_limit_value(
            title=self.tr("Attach File Warning Limit"),
            label=self.tr("Warn when attaching file larger than (bytes):"),
            current=current,
        )
        if value is None:
            return
        set_attach_file_warning_limit_bytes(value)
        self._refresh_edit_limits_menu_entries()
        self.statusBar.showMessage(self.tr("Updated attach file warning limit"), 2000)

    def _bind_validation_status(self, tab) -> None:
        """Connect/disconnect the permanent validation status label to *tab*."""
        if self._bound_validation_tab is not None:
            try:
                self._bound_validation_tab.validationChanged.disconnect(self._on_tab_validation_changed)
            except (RuntimeError, TypeError):
                pass
        self._bound_validation_tab = tab
        if tab is not None:
            tab.validationChanged.connect(self._on_tab_validation_changed)
            self._on_tab_validation_changed(tab.issue_index)
        else:
            self._validation_status_label.setVisible(False)

    def _on_tab_validation_changed(self, issue_index) -> None:
        from documents.tab_status import format_validation_status

        text = format_validation_status(issue_index)
        if text:
            self._validation_status_label.setText(text)
            self._validation_status_label.setVisible(True)
        else:
            self._validation_status_label.setVisible(False)

    # ─────────────────────────────────────────────────────────────────────

    def _on_validation_issue_activated(self, issue, *, edit: bool = False) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        tab.goto_validation_issue(issue, edit=edit)

    def _setup_monospace_action(self) -> None:
        self.viewMonospaceFieldsAction = QAction("Monospace Names && Values", self)
        self.viewMonospaceFieldsAction.setCheckable(True)
        self.viewMonospaceFieldsAction.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.viewMonospaceFieldsAction.setChecked(self.fonts.profile.monospace_fields_enabled)

        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.viewMonospaceFieldsAction)

    def _setup_font_actions(self) -> None:
        self.viewSelectRegularFontAction = QAction("Select Regular Font...", self)
        self.viewSelectMonospaceFontAction = QAction("Select Monospace Font...", self)

        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.viewSelectRegularFontAction)
        self.viewMenu.addAction(self.viewSelectMonospaceFontAction)

    def setup_model(self, yaml_filename: str):
        if not yaml_filename:
            return
        self._open_path(yaml_filename)

    def _current_tab(self) -> JsonTab | None:
        tab = self.tabWidget.currentWidget()
        return tab if isinstance(tab, JsonTab) else None

    def _current_view(self) -> QTreeView | None:
        tab = self._current_tab()
        return tab.view if tab is not None else None

    def setup_connections(self):
        setup_main_window_connections(self)

    def _theme_tabs(self) -> list[JsonTab]:
        tabs: list[JsonTab] = []
        for i in range(self.tabWidget.count()):
            widget = self.tabWidget.widget(i)
            if isinstance(widget, JsonTab):
                tabs.append(widget)
        return tabs

    def _on_theme_applied(self, theme, icon_provider) -> None:
        self._theme = theme
        self._icon_provider = icon_provider
        for tab in self._theme_tabs():
            tab.set_theme(theme, icon_provider)

    def _apply_theme(self, theme) -> None:
        self._theme_controller.apply_theme(theme)

    def _setup_theme_menu(self) -> None:
        self._theme_controller.setup_theme_menu(self.viewMenu)
        self._theme_follow_action = self._theme_controller.follow_action

    def _rebuild_theme_menu_entries(self) -> None:
        self._theme_controller.rebuild_theme_menu_entries()

    def _refresh_theme_menu_checks(self) -> None:
        self._theme_controller.refresh_theme_menu_checks()

    def _on_theme_selected(self, name: str) -> None:
        self._theme_controller.on_theme_selected(name)

    def _on_follow_system_toggled(self, checked: bool) -> None:
        self._theme_controller.on_follow_system_toggled(checked)

    def _open_themes_folder(self) -> None:
        self._theme_controller.open_themes_folder()

    def _refresh_theme_watcher_paths(self) -> None:
        self._theme_controller.refresh_theme_watcher_paths()

    def _on_theme_fs_event(self, _path: str) -> None:
        self._theme_controller.on_theme_fs_event(_path)

    def _reload_themes_from_disk(self) -> None:
        self._theme_controller.reload_themes()

    def _on_system_color_scheme_changed(self, *_args) -> None:
        self._theme_controller.on_system_color_scheme_changed(*_args)

    def _bind_undo_signals(self, tab: JsonTab | None) -> None:
        bind_undo_signals(self, tab)

    def _on_tab_changed(self, _index: int) -> None:
        tab = self._current_tab()
        self._bind_undo_signals(tab)
        self._bind_validation_status(tab)
        self.validation_dock.attach_tab(tab)
        if tab is not None:
            tab.resize_key_columns()
        if self._history_dialog is not None and self._history_dialog.isVisible():
            if tab is not None and self._history_view is not None:
                self._history_view.setStack(tab.undo_stack)
        self.update_actions()

    def _add_tab(self, *, data=None, file_path: str | None = None, save_format: str | None = None) -> JsonTab | None:
        from state.validation_settings import auto_rescan_enabled

        try:
            tab = JsonTab(
                self.update_actions,
                self.statusBar.showMessage,
                data=data,
                file_path=file_path,
                show_root=True,
                parent=self,
                permanent_message_callback=lambda msg: self.statusBar.showMessage(msg, 0),
                theme=self._theme,
                icon_provider=self._icon_provider,
                save_format=save_format,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to create tab:\n{exc}")
            return None

        # Apply the global auto-rescan setting to the new tab.
        tab.set_auto_rescan(auto_rescan_enabled())

        tab_index = self.tabWidget.addTab(tab, tab.display_name())
        self.tabWidget.setCurrentIndex(tab_index)
        self.fonts.subscribe(tab)
        tab.dirtyChanged.connect(lambda _dirty, t=tab: self._on_tab_dirty(t))

        tab.view.expandAll()
        tab.resize_key_columns()
        if tab.model.show_root:
            source_index = tab.model.index(0, 0, QModelIndex())
            tab.view.setCurrentIndex(tab._source_to_view(source_index))
        view_state.restore(tab)
        # Re-broadcast: ``view_state.restore`` may have rewritten ``_font_pt``
        # from a previously-saved per-tab value; the global controller wins.
        self.fonts.subscribe(tab)

        self._bind_undo_signals(tab)
        self.update_actions()
        return tab

    def _on_tab_dirty(self, tab: JsonTab) -> None:
        index = self.tabWidget.indexOf(tab)
        if index >= 0:
            self.tabWidget.setTabText(index, tab.display_name())
        self.update_actions()

    def _open_path(self, path: str) -> bool:
        resolved = str(Path(path).resolve())
        self.statusBar.showMessage(f"Loading: {resolved}", 0)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self.statusBar.showMessage(f"Open failed: {resolved}", 3000)
            QMessageBox.critical(self, "Open failed", f"Could not open {resolved}:\n{exc}")
            return False

        tab = self._add_tab(data=data, file_path=resolved, save_format=source_format)
        if tab is None:
            return False
        push_recent(self, resolved)
        self.statusBar.showMessage(f"Opened: {resolved}", 2000)
        return True

    def _save_tab(self, tab: JsonTab, *, save_as: bool = False) -> bool:
        from state.validation_settings import clear_schema_path

        if tab.is_read_only:
            return False
        old_path = tab.file_path
        ok = tab.save_as() if save_as else tab.save()
        if not ok:
            return False
        if save_as and isinstance(old_path, str) and tab.file_path and old_path != tab.file_path:
            view_state.discard(old_path)
            clear_schema_path(Path(old_path))
        view_state.save(tab)
        if tab.file_path:
            push_recent(self, tab.file_path)
        self._on_tab_dirty(tab)
        return True

    def _confirm_close(self, tab: JsonTab) -> bool:
        return confirm_close(self, tab)

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open",
            "",
            "All supported (*.json *.jsonl *.ndjson *.yaml *.yml);;JSON (*.json);;JSON Lines (*.jsonl *.ndjson);;YAML (*.yaml *.yml)",
        )
        if not path:
            return
        self._open_path(path)

    def save_file(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        self._save_tab(tab, save_as=False)

    def save_file_as(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        self._save_tab(tab, save_as=True)

    def create_new_file(self):
        self._add_tab(data={}, file_path=None)

    def close_tab(self, index: int) -> None:
        widget = self.tabWidget.widget(index)
        if isinstance(widget, JsonTab) and not self._confirm_close(widget):
            return
        if isinstance(widget, JsonTab):
            self._schema_tab_pool.unregister(widget)
            view_state.save(widget)
        if widget is self._bound_undo_tab:
            self._bind_undo_signals(None)
        self.tabWidget.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        self.update_actions()
        # Re-bind to whatever tab is now current (if any).
        current = self._current_tab()
        self._bind_undo_signals(current)
        self._bind_validation_status(current)
        self.validation_dock.attach_tab(current)

    def insert_child(self):
        tab = self._current_tab()
        if tab is None:
            return

        if not tab.insert_child():
            return

        self.update_actions()

    def insert_column(self):
        return False

    def insert_row_before(self):
        tab = self._current_tab()
        if tab is None:
            return

        if not tab.insert_sibling_before():
            return

        self.update_actions()

    def insert_row_after(self):
        tab = self._current_tab()
        if tab is None:
            return

        if not tab.insert_sibling_after():
            return

        self.update_actions()

    def insert_row(self):
        # Backward-compatible helper used by old call sites.
        self.insert_row_after()

    def remove_column(self):
        view = self._current_view()
        if view is None:
            return False

        model = view.model()
        column = view.selectionModel().currentIndex().column()
        changed = model.removeColumn(column)

        if changed:
            self.update_actions()

        return changed

    def remove_row(self):
        view = self._current_view()
        if view is None:
            return

        if delete_selection(view):
            self.update_actions()

    def expand_all(self) -> None:
        view = self._current_view()
        if view is None:
            return
        expand_all(view)

    def collapse_all(self) -> None:
        view = self._current_view()
        if view is None:
            return
        collapse_all(view)

    def zoom_in(self) -> None:
        self.fonts.zoom_in()

    def zoom_out(self) -> None:
        self.fonts.zoom_out()

    def reset_zoom(self) -> None:
        self.fonts.reset_zoom()

    def set_editor_font_point_size(self, point_size: int) -> None:
        self.fonts.set_point_size(point_size)

    def toggle_monospace_fields(self, enabled: bool) -> None:
        self.fonts.set_monospace_fields_enabled(enabled)

    def set_regular_font_family(self, family: str) -> None:
        self.fonts.set_regular_family(family)

    def set_monospace_font_family(self, family: str) -> None:
        self.fonts.set_monospace_family(family)

    def select_regular_font(self) -> None:
        tab = self._current_tab()
        seed = QFont(tab.view.font()) if tab is not None else QFont(self.font())
        if self.fonts.profile.regular_family:
            seed.setFamily(self.fonts.profile.regular_family)
        seed = self._normalize_font_for_dialog(seed)
        chosen, ok = self._unpack_font_dialog_result(QFontDialog.getFont(seed, self, "Select Regular Font"))
        if not ok or chosen is None:
            return
        self.fonts.set_regular_family(chosen.family())

    def select_monospace_font(self) -> None:
        seed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if self.fonts.profile.monospace_family:
            seed.setFamily(self.fonts.profile.monospace_family)
        seed = self._normalize_font_for_dialog(seed)
        chosen, ok = self._unpack_font_dialog_result(QFontDialog.getFont(seed, self, "Select Monospace Font"))
        if not ok or chosen is None:
            return
        self.fonts.set_monospace_family(chosen.family())

    def update_actions(self):
        update_main_window_actions(self)

    def copy_action(self):
        view = self._current_view()
        if view is None:
            return

        if copy_selection(view):
            self.statusBar.showMessage("Copied selection", 1500)
        else:
            self.statusBar.showMessage("Nothing to copy", 1500)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._theme_controller.shutdown()
        for i in range(self.tabWidget.count() - 1, -1, -1):
            widget = self.tabWidget.widget(i)
            if isinstance(widget, JsonTab) and not self._confirm_close(widget):
                event.ignore()
                return
            if isinstance(widget, JsonTab):
                view_state.save(widget)
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/fullscreen", self.isFullScreen())
        self._settings.setValue("window/maximized", self.isMaximized())
        self._settings.setValue("validation/dock_state", self.saveState())
        self._settings.setValue("validation/dock_visible", self.validation_dock.isVisible())
        super().closeEvent(event)
