# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMenu, QMessageBox, QTreeView, QUndoView

import state.view_state as view_state
from app.close_confirm import confirm_close
from app.history import bind_undo_signals, setup_history_menu
from app.main_window_actions import setup_connections as setup_main_window_connections
from app.main_window_actions import update_actions as update_main_window_actions
from app.recent_files import push_recent, refresh_recent_menu
from app.theme_controller import ThemeController
from documents.tab import JsonTab
from io_formats.load import load_file_with_format
from mainwindow import Ui_MainWindow
from settings import APPLICATION_ID
from tree_actions.clipboard import copy_selection
from tree_actions.structure import collapse_all, delete_selection, expand_all


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._history_dialog: QDialog | None = None
        self._history_view: QUndoView | None = None
        self._bound_undo_tab: JsonTab | None = None
        self._settings = QSettings(APPLICATION_ID, "app")
        self._theme_controller = ThemeController(self, self._on_theme_applied)
        self._theme_registry = self._theme_controller.registry
        self._theme = self._theme_controller.theme
        self._icon_provider = self._theme_controller.icon_provider
        self._theme_follow_action = self._theme_controller.follow_action
        self._recent_menu = QMenu("Recent", self)
        self.fileMenu.insertMenu(self.appExitAction, self._recent_menu)
        self.fileMenu.insertSeparator(self.appExitAction)
        refresh_recent_menu(self)
        setup_history_menu(self)
        self.setup_model(yaml_filename)
        self.setup_connections()

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
        tab.dirtyChanged.connect(lambda _dirty, t=tab: self._on_tab_dirty(t))

        tab.view.expandAll()
        tab.resize_key_columns()
        if tab.model.show_root:
            source_index = tab.model.index(0, 0, QModelIndex())
            tab.view.setCurrentIndex(tab._source_to_view(source_index))
        view_state.restore(tab)

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
        self._bind_undo_signals(self._current_tab())

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
        tab = self._current_tab()
        if tab is None:
            return
        tab.zoom_in()

    def zoom_out(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        tab.zoom_out()

    def reset_zoom(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        tab.zoom_reset()

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
        for i in range(self.tabWidget.count() - 1, -1, -1):
            widget = self.tabWidget.widget(i)
            if isinstance(widget, JsonTab) and not self._confirm_close(widget):
                event.ignore()
                return
            if isinstance(widget, JsonTab):
                view_state.save(widget)
        super().closeEvent(event)
