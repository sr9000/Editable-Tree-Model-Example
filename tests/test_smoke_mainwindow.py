"""Smoke tests for MainWindow.

These tests instantiate the real MainWindow and exercise the user-facing
actions to catch integration bugs (such as the QStatusBar shadowing the
QMainWindow.statusBar() method that broke "Create new file").
"""

import pytest
from PySide6.QtWidgets import QApplication, QStatusBar

from json_tab import JsonTab
from ui import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp):
    win = MainWindow(yaml_filename="")
    yield win
    win.close()
    win.deleteLater()


def test_mainwindow_constructs(main_window):
    """MainWindow can be constructed without errors."""
    assert main_window is not None
    assert main_window.tabWidget is not None
    assert main_window.tabWidget.count() == 0


def test_mainwindow_status_bar_is_usable(main_window):
    """`self.statusBar` must expose a showMessage callable.

    Regression: Ui_MainWindow assigns ``self.statusBar = QStatusBar(...)``,
    which shadows ``QMainWindow.statusBar()``. Code that called
    ``self.statusBar()`` raised "QStatusBar object is not callable".
    """
    assert isinstance(main_window.statusBar, QStatusBar)
    # showMessage must be callable with (text, timeout)
    main_window.statusBar.showMessage("hello", 1000)
    assert main_window.statusBar.currentMessage() == "hello"


def test_create_new_file_action_opens_tab(main_window):
    """Triggering 'Create new file' must open a JsonTab without errors."""
    assert main_window.tabWidget.count() == 0

    # Trigger via the same code path the menu uses.
    main_window.create_new_file()

    assert main_window.tabWidget.count() == 1
    tab = main_window.tabWidget.widget(0)
    assert isinstance(tab, JsonTab)
    assert tab.model.rowCount() > 0


def test_create_multiple_new_file_tabs(main_window):
    """Multiple invocations should each add a new tab."""
    main_window.create_new_file()
    main_window.create_new_file()
    assert main_window.tabWidget.count() == 2

    main_window.close_tab(0)
    assert main_window.tabWidget.count() == 1
