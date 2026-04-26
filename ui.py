# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMenu, QMessageBox, QTreeView, QUndoView, QVBoxLayout

import view_state
from file_io import load_file_with_format
from json_tab import JsonTab
from mainwindow import Ui_MainWindow
from settings import APPLICATION_ID
from tree_view import collapse_all, copy_selection, delete_selection, expand_all


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._history_dialog: QDialog | None = None
        self._history_view: QUndoView | None = None
        self._bound_undo_tab: JsonTab | None = None
        self._settings = QSettings(APPLICATION_ID, "app")
        self._recent_menu = QMenu("Recent", self)
        self.fileMenu.insertMenu(self.appExitAction, self._recent_menu)
        self.fileMenu.insertSeparator(self.appExitAction)
        self._refresh_recent_menu()
        self._setup_history_menu()
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
        self.appExitAction.triggered.connect(self.close)

        self.fileCreateNewAction.triggered.connect(self.create_new_file)
        self.fileOpenAction.triggered.connect(self.open_file_dialog)
        self.fileSaveAction.triggered.connect(self.save_file)
        self.fileSaveAsAction.triggered.connect(self.save_file_as)

        self.actionsMenu.aboutToShow.connect(self.update_actions)
        self.rowInsertAction.triggered.connect(self.insert_row_before)
        self.rowInsertAfterAction.triggered.connect(self.insert_row_after)
        self.rowRemoveAction.triggered.connect(self.remove_row)

        self.viewExpandAllAction.triggered.connect(self.expand_all)
        self.viewCollapseAllAction.triggered.connect(self.collapse_all)
        self.viewZoomInAction.triggered.connect(self.zoom_in)
        self.viewZoomOutAction.triggered.connect(self.zoom_out)
        self.viewResetZoomAction.triggered.connect(self.reset_zoom)

        self.update_actions()

        self.tabWidget.tabCloseRequested.connect(self.close_tab)
        self.tabWidget.currentChanged.connect(self._on_tab_changed)

    def _setup_history_menu(self) -> None:
        self.historyMenu = self.menuBar.addMenu("&History")

        self.undoAction = QAction("&Undo", self)
        self.undoAction.setShortcut(QKeySequence.StandardKey.Undo)
        self.undoAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.undoAction.triggered.connect(self._do_undo)
        self.undoAction.setEnabled(False)

        self.redoAction = QAction("&Redo", self)
        self.redoAction.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Y")])
        self.redoAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.redoAction.triggered.connect(self._do_redo)
        self.redoAction.setEnabled(False)

        self.showHistoryAction = QAction("Show History...", self)
        self.showHistoryAction.triggered.connect(self._show_history_dialog)
        self.showHistoryAction.setEnabled(False)

        self.historyMenu.addAction(self.undoAction)
        self.historyMenu.addAction(self.redoAction)
        self.historyMenu.addSeparator()
        self.historyMenu.addAction(self.showHistoryAction)

    def _bind_undo_signals(self, tab: JsonTab | None) -> None:
        # Disconnect previously-bound stack so stale signals don't toggle our actions.
        previous = self._bound_undo_tab
        if previous is not None:
            try:
                previous.undo_stack.canUndoChanged.disconnect(self.undoAction.setEnabled)
                previous.undo_stack.canRedoChanged.disconnect(self.redoAction.setEnabled)
            except (TypeError, RuntimeError):
                pass

        self._bound_undo_tab = tab

        if tab is not None:
            tab.undo_stack.canUndoChanged.connect(self.undoAction.setEnabled)
            tab.undo_stack.canRedoChanged.connect(self.redoAction.setEnabled)
            self.undoAction.setEnabled(tab.undo_stack.canUndo())
            self.redoAction.setEnabled(tab.undo_stack.canRedo())
            self.showHistoryAction.setEnabled(True)
        else:
            self.undoAction.setEnabled(False)
            self.redoAction.setEnabled(False)
            self.showHistoryAction.setEnabled(False)

    def _do_undo(self) -> None:
        tab = self._current_tab()
        if tab is not None:
            tab.undo_stack.undo()

    def _do_redo(self) -> None:
        tab = self._current_tab()
        if tab is not None:
            tab.undo_stack.redo()

    def _show_history_dialog(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return

        if self._history_dialog is None:
            self._history_dialog = QDialog(self)
            self._history_dialog.setWindowTitle("Undo / Redo History")
            self._history_dialog.resize(320, 400)
            layout = QVBoxLayout(self._history_dialog)
            self._history_view = QUndoView(self._history_dialog)
            self._history_view.setEmptyLabel("<initial state>")
            layout.addWidget(self._history_view)

        self._history_view.setStack(tab.undo_stack)
        self._history_dialog.show()
        self._history_dialog.raise_()
        self._history_dialog.activateWindow()

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
        self._push_recent(resolved)
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
            self._push_recent(tab.file_path)
        self._on_tab_dirty(tab)
        return True

    def _confirm_close(self, tab: JsonTab) -> bool:
        if not tab.is_dirty:
            return True
        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes to {tab.display_name().replace(' *', '')}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self._save_tab(tab)
        return True

    def _recent_files(self) -> list[str]:
        return self._settings.value("recent_files", [], type=list)

    def _push_recent(self, path: str) -> None:
        resolved = str(Path(path).resolve())
        recent = [resolved] + [p for p in self._recent_files() if p != resolved]
        self._settings.setValue("recent_files", recent[:8])
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        for path in self._recent_files():
            if not Path(path).exists():
                continue
            action = self._recent_menu.addAction(path)
            action.triggered.connect(lambda _checked=False, p=path: self._open_path(p))
        self._recent_menu.setEnabled(bool(self._recent_menu.actions()))

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
        tab = self._current_tab()
        has_tab = tab is not None
        has_valid_index = bool(tab and tab.view.selectionModel().currentIndex().isValid())

        self.fileSaveAction.setEnabled(has_tab)
        self.fileSaveAsAction.setEnabled(has_tab)
        self.rowInsertAction.setEnabled(has_valid_index)
        self.rowInsertAfterAction.setEnabled(has_valid_index)
        self.rowRemoveAction.setEnabled(has_valid_index)
        self.viewExpandAllAction.setEnabled(has_tab)
        self.viewCollapseAllAction.setEnabled(has_tab)
        self.viewZoomInAction.setEnabled(has_tab)
        self.viewZoomOutAction.setEnabled(has_tab)
        self.viewResetZoomAction.setEnabled(has_tab)

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
