from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPoint
from PySide6.QtWidgets import QApplication, QMenu

from documents.tab import JsonTab
from tree_actions.context_menu import show_context_menu
from tree_actions.structure import collapse_selection_recursive, expand_selection_recursive


def _set_current_source_row(tab: JsonTab, source_index: QModelIndex) -> None:
    view_index = tab.view_controller.source_to_view(source_index)
    sm = tab.view.selectionModel()
    sm.select(
        view_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    sm.setCurrentIndex(view_index, QItemSelectionModel.SelectionFlag.NoUpdate)


def _collect_labels(menu: QMenu) -> set[str]:
    labels: set[str] = set()
    for action in menu.actions():
        submenu = action.menu()
        if submenu is not None:
            labels |= _collect_labels(submenu)
        elif action.text():
            labels.add(action.text())
    return labels


def test_context_menu_hides_inactive_actions_without_selection(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"x": 1}}, show_root=True)
    qtbot.addWidget(tab)
    tab.show()
    QApplication.processEvents()

    menu = show_context_menu(tab.view, QPoint(-100, -100), execute=False)
    assert menu is not None
    labels = _collect_labels(menu)

    assert "Copy" not in labels
    assert "Cut" not in labels
    assert "Delete" not in labels
    assert "Move Up" not in labels


def test_context_menu_uses_recursive_expand_collapse_labels(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"x": 1}, "tail": 2}, show_root=True)
    qtbot.addWidget(tab)
    tab.show()
    tab.view.expandAll()
    QApplication.processEvents()

    root = tab.model.index(0, 0, QModelIndex())
    obj_row = tab.model.index(0, 0, root)
    _set_current_source_row(tab, obj_row)
    position = tab.view.visualRect(tab.view_controller.source_to_view(obj_row)).center()

    menu = show_context_menu(tab.view, position, execute=False)
    assert menu is not None
    labels = _collect_labels(menu)

    assert "Expand Recursively" in labels
    assert "Collapse Recursively" in labels
    assert "Expand All" not in labels
    assert "Collapse All" not in labels


def test_recursive_expand_collapse_scope_to_selected_subtree(qtbot):
    tab = JsonTab(lambda *_: None, data={"a": {"x": {"k": 1}}, "b": {"y": 2}}, show_root=True)
    qtbot.addWidget(tab)
    tab.show()
    tab.view.expandAll()
    QApplication.processEvents()

    root = tab.model.index(0, 0, QModelIndex())
    a_row = tab.model.index(0, 0, root)
    b_row = tab.model.index(1, 0, root)
    a_child = tab.model.index(0, 0, a_row)

    tab.view.collapseAll()
    _set_current_source_row(tab, a_row)
    assert expand_selection_recursive(tab.view)

    assert tab.view.isExpanded(tab.view_controller.source_to_view(a_row))
    assert tab.view.isExpanded(tab.view_controller.source_to_view(a_child))
    assert not tab.view.isExpanded(tab.view_controller.source_to_view(b_row))

    tab.view.expandAll()
    assert tab.view.isExpanded(tab.view_controller.source_to_view(b_row))
    _set_current_source_row(tab, a_row)
    assert collapse_selection_recursive(tab.view)

    assert not tab.view.isExpanded(tab.view_controller.source_to_view(a_row))
    assert tab.view.isExpanded(tab.view_controller.source_to_view(b_row))
