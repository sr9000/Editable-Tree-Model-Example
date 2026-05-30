from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication, QMenu

from documents.tab import JsonTab
from tree_actions.context_menu import show_context_menu
from tree_actions.selection import _index_path, _to_source_index


def _action_by_text(menu: QMenu, text: str):
    for action in menu.actions():
        submenu = action.menu()
        if submenu is not None:
            found = _action_by_text(submenu, text)
            if found is not None:
                return found
        elif action.text() == text:
            return action
    return None


def test_context_menu_adds_goto_only_when_search_active(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"needle": 1}, "tail": 2}, show_root=True)
    qtbot.addWidget(tab)
    tab.show()
    tab.view.expandAll()
    QApplication.processEvents()

    source_row = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0, QModelIndex()))
    pos = tab.view.visualRect(tab._source_to_view(source_row)).center()

    menu = show_context_menu(tab.view, pos, execute=False)
    assert menu is not None
    assert _action_by_text(menu, "Go To") is None

    tab.view_controller.search_edit.setText("needle")
    tab._apply_filter()
    QApplication.processEvents()

    menu = show_context_menu(tab.view, pos, execute=False)
    assert menu is not None
    assert _action_by_text(menu, "Go To") is not None


def test_goto_clears_search_and_focuses_clicked_field(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"needle": 1, "other": 2}, "tail": 3}, show_root=True)
    qtbot.addWidget(tab)
    tab.show()
    tab.view.expandAll()
    QApplication.processEvents()

    target_source = tab.data_store.model.index(
        0, 0, tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0, QModelIndex()))
    )
    target_path = _index_path(target_source)

    tab.view_controller.search_edit.setText("needle")
    tab._apply_filter()
    QApplication.processEvents()

    target_view = tab._source_to_view(target_source)
    assert target_view.isValid()
    pos = tab.view.visualRect(target_view).center()

    menu = show_context_menu(tab.view, pos, execute=False)
    assert menu is not None
    action = _action_by_text(menu, "Go To")
    assert action is not None

    action.trigger()
    QApplication.processEvents()

    assert tab.view_controller.search_edit.text() == ""
    current_source = _to_source_index(tab.view.currentIndex())
    assert _index_path(current_source.siblingAtColumn(0)) == target_path
