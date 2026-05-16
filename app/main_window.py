# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from pathlib import Path

from PySide6.QtCore import QByteArray, QModelIndex, QSettings, Qt
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFontDialog,
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
from app.theme_controller import ThemeController
from app.validation_dock import ValidationDock
from documents.tab import JsonTab
from io_formats.load import load_file_with_format
from mainwindow import Ui_MainWindow
from settings import APPLICATION_ID
from tree_actions.clipboard import copy_selection
from tree_actions.structure import collapse_all, delete_selection, expand_all


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
        self._history_dialog: QDialog | None = None
        self._history_view: QUndoView | None = None
        self._bound_undo_tab: JsonTab | None = None
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
        self._theme_follow_action = self._theme_controller.follow_action
        self._recent_menu = QMenu("Recent", self)
        self.fileMenu.insertMenu(self.appExitAction, self._recent_menu)
        self.fileMenu.insertSeparator(self.appExitAction)
        refresh_recent_menu(self)
        self._setup_validation_dock()
        self._setup_font_actions()
        self._setup_monospace_action()
        setup_history_menu(self)
        self.setup_model(yaml_filename)
        self.setup_connections()

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
        from state.validation_settings import write_schema_ref_str
        from validation.schema_source import SchemaRef, load_schema, load_schema_from_url

        tab = self._current_tab()
        if tab is None:
            return

        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QHBoxLayout,
            QLabel as _QLabel,
            QLineEdit,
            QPushButton as _QPushButton,
            QVBoxLayout,
        )

        class _AttachDialog(QDialog):
            def __init__(self, parent=None, start_dir=""):
                super().__init__(parent)
                self.setWindowTitle(self.tr("Attach JSON Schema"))
                self.resize(540, 110)
                lbl = _QLabel(self.tr("Schema file path or URL (http/https):"))
                self._edit = QLineEdit()
                self._edit.setPlaceholderText("https://…  or  /path/to/schema.json")
                browse = _QPushButton(self.tr("Browse…"))
                browse.clicked.connect(self._browse)
                self._start_dir = start_dir
                row = QHBoxLayout()
                row.addWidget(self._edit, 1)
                row.addWidget(browse)
                buttons = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout = QVBoxLayout(self)
                layout.addWidget(lbl)
                layout.addLayout(row)
                layout.addWidget(buttons)

            def _browse(self):
                p, _ = QFileDialog.getOpenFileName(
                    self,
                    self.tr("Select Schema File"),
                    self._start_dir,
                    "JSON Schema (*.json *.yaml *.yml);;All files (*)",
                )
                if p:
                    self._edit.setText(p)

            def value(self) -> str:
                return self._edit.text().strip()

        dlg = _AttachDialog(self, tab.file_path or "")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        ref_str = dlg.value()
        if not ref_str:
            return

        lo = ref_str.lower()
        is_url = lo.startswith("http://") or lo.startswith("https://")

        if is_url:
            loaded = load_schema_from_url(ref_str)
            if loaded is None:
                self.statusBar.showMessage(self.tr(f"Could not fetch schema: {ref_str}"), 3000)
                return
            ref = SchemaRef(path=None, inline=dict(loaded), origin="manual", url=ref_str)
        else:
            import os
            if not os.path.exists(ref_str):
                self.statusBar.showMessage(self.tr(f"File not found: {ref_str}"), 3000)
                return
            file_ref = SchemaRef(path=Path(ref_str), inline=None, origin="manual")
            loaded = load_schema(file_ref)
            if loaded is None:
                self.statusBar.showMessage(self.tr(f"Could not load schema: {ref_str}"), 3000)
                return
            ref = SchemaRef(path=Path(ref_str), inline=dict(loaded), origin="manual")

        tab.set_schema(ref)
        if tab.file_path:
            write_schema_ref_str(Path(tab.file_path), ref_str)
        self.statusBar.showMessage(self.tr(f"Schema attached: {ref_str}"), 2000)

    def _on_reload_schema_requested(self) -> None:
        from validation.schema_source import SchemaRef, load_schema, load_schema_from_url

        tab = self._current_tab()
        if tab is None:
            return
        ref = tab.schema_ref
        url = getattr(ref, "url", None)
        if url is not None:
            loaded = load_schema_from_url(url)
            if loaded is None:
                self.statusBar.showMessage(self.tr("Reload failed: could not fetch schema URL"), 3000)
                return
            tab.set_schema(SchemaRef(path=None, inline=dict(loaded), origin=ref.origin, url=url))
            self.statusBar.showMessage(self.tr("Schema reloaded"), 2000)
            return
        if ref.path is None:
            return
        origin = ref.origin
        new_ref = SchemaRef(path=ref.path, inline=None, origin=origin)
        loaded = load_schema(new_ref)
        if loaded is None:
            self.statusBar.showMessage(self.tr("Reload failed: schema file not found"), 3000)
            return
        tab.set_schema(SchemaRef(path=ref.path, inline=dict(loaded), origin=origin))
        self.statusBar.showMessage(self.tr("Schema reloaded"), 2000)

    def _on_open_schema_file_requested(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        # URL-based schema: open in browser
        url = getattr(tab.schema_ref, "url", None)
        if url is not None:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(url))
            return
        if tab.schema_ref.path is None:
            return
        path = str(tab.schema_ref.path)
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
                severity="error",
                message="",
                instance_path=issue.schema_path,
                schema_path=(),
                kind="",
            )
            schema_tab.goto_validation_issue(fake_issue)

        url = getattr(tab.schema_ref, "url", None)
        if url is not None:
            # Check if we already have this URL open as a tab
            for i in range(self.tabWidget.count()):
                widget = self.tabWidget.widget(i)
                if isinstance(widget, JsonTab) and getattr(widget, "_schema_url_source", None) == url:
                    self.tabWidget.setCurrentIndex(i)
                    _navigate(widget)
                    return
            # Download and open in a new in-memory tab
            from validation.schema_source import load_schema_from_url
            loaded = load_schema_from_url(url)
            if loaded is None:
                self.statusBar.showMessage(self.tr("Could not fetch schema for navigation"), 3000)
                return
            schema_tab = self._add_tab(data=dict(loaded), file_path=None)
            if schema_tab is None:
                return
            # Tag so we can reuse this tab next time
            schema_tab._schema_url_source = url
            # Give it a readable title
            short = url.rstrip("/").rsplit("/", 1)[-1] or url
            idx = self.tabWidget.indexOf(schema_tab)
            if idx >= 0:
                self.tabWidget.setTabText(idx, short)
                self.tabWidget.setTabToolTip(idx, url)
            _navigate(schema_tab)
            return

        if tab.schema_ref.path is None:
            return
        import os
        path = str(tab.schema_ref.path)
        if not os.path.exists(path):
            self.statusBar.showMessage(self.tr("Schema file not found"), 3000)
            return
        self._open_path(path)
        schema_tab = self._current_tab()
        _navigate(schema_tab)

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
        self._settings.setValue("validation/dock_state", self.saveState())
        self._settings.setValue("validation/dock_visible", self.validation_dock.isVisible())
        super().closeEvent(event)
