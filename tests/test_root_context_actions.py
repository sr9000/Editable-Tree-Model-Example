"""Tests for context menu actions available on the fake root node."""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPoint
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from documents.tab import JsonTab
from tree_actions.context_menu import show_context_menu


def _current_tab(win: MainWindow) -> JsonTab:
    tab = win._current_tab()
    assert isinstance(tab, JsonTab)
    return tab


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        w = win.tabWidget.widget(i)
        if isinstance(w, JsonTab):
            w.data_store.undo_stack.setClean()
    win.close()
    win.deleteLater()
    QApplication.processEvents()


def _select_root(tab: JsonTab) -> None:
    """Select the visible fake-root row."""
    root_idx = tab.data_store.model.index(0, 0, QModelIndex())
    view_idx = tab._source_to_view(root_idx)
    sm = tab.data_store.view.selectionModel()
    sm.select(view_idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    sm.setCurrentIndex(view_idx, QItemSelectionModel.SelectionFlag.NoUpdate)


def _menu_action_texts(menu) -> list[str]:
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def test_expand_recursively_available_when_root_selected(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"a": {"b": 1}})
        tab = _current_tab(win)
        _select_root(tab)

        menu = show_context_menu(tab.data_store.view, QPoint(0, 0), execute=False)
        assert menu is not None
        texts = _menu_action_texts(menu)
        assert "Expand Recursively" in texts
    finally:
        _cleanup(win)


def test_collapse_recursively_available_when_root_selected(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"a": {"b": 1}})
        tab = _current_tab(win)
        _select_root(tab)

        menu = show_context_menu(tab.data_store.view, QPoint(0, 0), execute=False)
        assert menu is not None
        texts = _menu_action_texts(menu)
        assert "Collapse Recursively" in texts
    finally:
        _cleanup(win)


def test_switch_case_submenu_available_when_root_selected(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"myKey": 1})
        tab = _current_tab(win)
        _select_root(tab)

        menu = show_context_menu(tab.data_store.view, QPoint(0, 0), execute=False)
        assert menu is not None
        texts = _menu_action_texts(menu)
        assert "Switch Case" in texts or any("Switch" in t for t in texts)
    finally:
        _cleanup(win)


def test_expand_recursively_on_root_expands_all(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"a": {"b": {"c": 1}}})
        tab = _current_tab(win)
        tab.data_store.view.collapseAll()
        _select_root(tab)

        from tree_actions.structure import expand_selection_recursive

        result = expand_selection_recursive(tab.data_store.view)
        assert result is True
        # After expand-all, at least the root row is expanded
        root_view_idx = tab._source_to_view(tab.data_store.model.index(0, 0, QModelIndex()))
        assert tab.data_store.view.isExpanded(root_view_idx)
    finally:
        _cleanup(win)


def test_delete_still_unavailable_for_root(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"x": 1})
        tab = _current_tab(win)
        _select_root(tab)

        menu = show_context_menu(tab.data_store.view, QPoint(0, 0), execute=False)
        assert menu is not None
        texts = _menu_action_texts(menu)
        assert "Delete" not in texts
    finally:
        _cleanup(win)


def test_move_up_still_unavailable_for_root(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"x": 1})
        tab = _current_tab(win)
        _select_root(tab)

        menu = show_context_menu(tab.data_store.view, QPoint(0, 0), execute=False)
        assert menu is not None
        texts = _menu_action_texts(menu)
        assert "Move Up" not in texts
    finally:
        _cleanup(win)
