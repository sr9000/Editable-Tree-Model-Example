# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox, QTreeView, QUndoView, QVBoxLayout

from json_tab import JsonTab
from mainwindow import Ui_MainWindow
from tree_view import copy_selection, delete_selection


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._history_dialog: QDialog | None = None
        self._history_view: QUndoView | None = None
        self._bound_undo_tab: JsonTab | None = None
        self._setup_history_menu()
        self.setup_model(yaml_filename)
        self.setup_connections()

    def setup_model(self, yaml_filename: str):
        _ = yaml_filename
        pass

    def _current_tab(self) -> JsonTab | None:
        tab = self.tabWidget.currentWidget()
        return tab if isinstance(tab, JsonTab) else None

    def _current_view(self) -> QTreeView | None:
        tab = self._current_tab()
        return tab.view if tab is not None else None

    def setup_connections(self):
        self.appExitAction.triggered.connect(QCoreApplication.quit)

        self.fileCreateNewAction.triggered.connect(self.create_new_file)

        self.actionsMenu.aboutToShow.connect(self.update_actions)
        self.rowInsertAction.triggered.connect(self.insert_row_before)
        self.rowInsertAfterAction.triggered.connect(self.insert_row_after)
        self.rowRemoveAction.triggered.connect(self.remove_row)

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
        if self._history_dialog is not None and self._history_dialog.isVisible():
            if tab is not None and self._history_view is not None:
                self._history_view.setStack(tab.undo_stack)

    def create_new_file(self):
        try:
            tab = JsonTab(self.update_actions, self.statusBar.showMessage, self)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create new file:\n{e}")
            return

        tab_index = self.tabWidget.addTab(tab, "New Json")
        self.tabWidget.setCurrentIndex(tab_index)

        wg: JsonTab = self.tabWidget.currentWidget()

        wg.view.expandAll()
        for column in range(wg.model.columnCount() - 1):
            wg.view.resizeColumnToContents(column)

        self._bind_undo_signals(wg)

    def close_tab(self, index: int) -> None:
        widget = self.tabWidget.widget(index)
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

    def update_actions(self):
        pass

    def copy_action(self):
        view = self._current_view()
        if view is None:
            return

        if copy_selection(view):
            self.statusBar.showMessage("Copied selection", 1500)
        else:
            self.statusBar.showMessage("Nothing to copy", 1500)
