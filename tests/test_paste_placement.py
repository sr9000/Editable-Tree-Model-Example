"""Tests for placement-aware paste and paste-replace introduced with the
context-menu refactor."""

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QApplication, QTreeView

from documents.tab import JsonTab
from tree.model import JsonTreeModel
from tree_actions.paste import has_clipboard_entries, paste_after, paste_as_child, paste_before, paste_replace_value


def _select(view: QTreeView, idx) -> None:
    sm = view.selectionModel()
    sm.select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    sm.setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)


def _select_tab(tab: JsonTab, source_index) -> None:
    view_idx = tab.view_controller.source_to_view(source_index)
    tab.view.setCurrentIndex(view_idx)
    tab.view.selectionModel().select(
        view_idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
    )


def test_paste_before_inserts_at_sibling_row(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    b = model.index(1, 0, QModelIndex())
    _select(view, b)

    QApplication.clipboard().setText("99")
    assert paste_before(view)
    # Inserted between "a" and "b"
    keys = list(model.root_item.to_json().keys())
    assert keys.index("a") < keys.index("new_key") < keys.index("b")


def test_paste_after_inserts_after_sibling(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    a = model.index(0, 0, QModelIndex())
    _select(view, a)

    QApplication.clipboard().setText("99")
    assert paste_after(view)
    keys = list(model.root_item.to_json().keys())
    assert keys.index("a") < keys.index("new_key") < keys.index("b")


def test_paste_as_child_only_on_container(qtbot):
    model = JsonTreeModel({"obj": {"x": 1}, "leaf": 5})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    QApplication.clipboard().setText('{"y": 2}')

    leaf = model.index(1, 0, QModelIndex())
    _select(view, leaf)
    assert not paste_as_child(view)  # primitive: rejected

    obj = model.index(0, 0, QModelIndex())
    _select(view, obj)
    assert paste_as_child(view)
    assert model.get_item(obj).to_json() == {"x": 1, "y": 2}


def test_paste_replace_value_swaps_subtree(qtbot):
    tab = JsonTab(lambda *_: None, data={"target": {"old": 1}})
    qtbot.addWidget(tab)

    target = tab.model.index(0, 0, QModelIndex())
    _select_tab(tab, target)

    QApplication.clipboard().setText('{"new": [10, 20, 30]}')
    assert paste_replace_value(tab.view)
    assert tab.model.get_item(target).to_json() == [10, 20, 30]

    # Undo restores original subtree.
    tab.undo_stack.undo()
    assert tab.model.get_item(target).to_json() == {"old": 1}


def test_paste_replace_value_rejects_multiple_entries(qtbot):
    tab = JsonTab(lambda *_: None, data={"target": 1})
    qtbot.addWidget(tab)

    target = tab.model.index(0, 0, QModelIndex())
    _select_tab(tab, target)

    QApplication.clipboard().setText('{"a": 1, "b": 2}')
    # Multi-entry clipboard ⇒ ambiguous replace; refuse.
    assert not paste_replace_value(tab.view)
    assert tab.model.get_item(target).to_json() == 1


def test_has_clipboard_entries_reflects_clipboard(qtbot):
    QApplication.clipboard().clear()
    QApplication.clipboard().setText("")
    assert not has_clipboard_entries()
    QApplication.clipboard().setText('{"k": 1}')
    assert has_clipboard_entries()
