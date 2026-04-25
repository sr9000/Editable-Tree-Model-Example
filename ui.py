# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTreeView

from json_tab import JsonTab
from mainwindow import Ui_MainWindow
from tree_view import copy_selection, delete_selection


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
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

    def close_tab(self, index: int) -> None:
        widget = self.tabWidget.widget(index)
        self.tabWidget.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        self.update_actions()

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
