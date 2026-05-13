# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from pathlib import Path

from PySide6.QtCore import QByteArray, QModelIndex, QSettings, Qt
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import QDialog, QFileDialog, QFontDialog, QMainWindow, QMenu, QMessageBox, QTreeView, QUndoView

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
        self.validation_dock = ValidationDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.validation_dock)

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
        self.validation_dock.attach_tab(tab)
        if tab is not None:
            tab.resize_key_columns()
        if self._history_dialog is not None and self._history_dialog.isVisible():
            if tab is not None and self._history_view is not None:
                self._history_view.setStack(tab.undo_stack)
        self.update_actions()

    def _add_tab(self, *, data=None, file_path: str | None = None) -> JsonTab | None:
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
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to create tab:\n{exc}")
            return None

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

        tab = self._add_tab(data=data, file_path=resolved)
        if tab is None:
            return False
        tab.save_format = source_format
        push_recent(self, resolved)
        self.statusBar.showMessage(f"Opened: {resolved}", 2000)
        return True

    def _save_tab(self, tab: JsonTab, *, save_as: bool = False) -> bool:
        old_path = tab.file_path
        ok = tab.save_as() if save_as else tab.save()
        if not ok:
            return False
        if save_as and isinstance(old_path, str) and tab.file_path and old_path != tab.file_path:
            view_state.discard(old_path)
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
