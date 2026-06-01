from PySide6.QtCore import QModelIndex

from documents.tab import JsonTab
from tree.filter_proxy import TreeFilterProxy
from tree.model import JsonTreeModel
from tree_actions.structure import delete_selection


def test_tree_filter_proxy_keeps_ancestors_of_matching_leaf():
    model = JsonTreeModel({"foo": {"bar": [1, "needle"]}, "other": "x"})
    proxy = TreeFilterProxy()
    proxy.setSourceModel(model)

    proxy.set_filter_text("needle")

    assert proxy.rowCount(QModelIndex()) == 1
    foo = proxy.index(0, 0, QModelIndex())
    assert proxy.data(foo) == "foo"

    bar = proxy.index(0, 0, foo)
    assert proxy.data(bar) == "bar"

    assert proxy.rowCount(bar) == 1
    match_leaf = proxy.index(0, 0, bar)
    assert proxy.data(match_leaf) == "#2"


def test_json_tab_filter_is_debounced(qtbot):
    tab = JsonTab(lambda *_: None, data={"alpha": "one", "beta": "two"})
    qtbot.addWidget(tab)

    assert tab.view_controller.proxy.rowCount(QModelIndex()) == 2

    tab.view_controller.search_edit.setText("beta")
    qtbot.wait(50)
    assert tab.view_controller.proxy.rowCount(QModelIndex()) == 2

    qtbot.wait(300)
    assert tab.view_controller.proxy.rowCount(QModelIndex()) == 1
    assert tab.view_controller.proxy.data(tab.view_controller.proxy.index(0, 0, QModelIndex())) == "beta"


def test_delete_selection_targets_source_row_while_filtered(qtbot):
    tab = JsonTab(lambda *_: None, data={"root": {"arr": [1, "needle", 3]}, "other": "x"})
    qtbot.addWidget(tab)

    tab.view_controller.search_edit.setText("needle")
    qtbot.wait(350)

    root = tab.view_controller.proxy.index(0, 0, QModelIndex())
    arr = tab.view_controller.proxy.index(0, 0, root)
    leaf = tab.view_controller.proxy.index(0, 0, arr)
    assert leaf.isValid()

    tab.view.setCurrentIndex(leaf)
    assert delete_selection(tab.view)

    assert tab.model.root_item.to_json() == {"root": {"arr": [1, 3]}, "other": "x"}
