from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QTreeView

from model_actions import (
    action_duplicate,
    action_insert_row_after,
    action_insert_row_before,
    action_move_down,
    action_move_up,
    action_sort_keys,
)
from tree_model import JsonTreeModel


def test_insert_row_before_and_after(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    b = model.index(1, 0, QModelIndex())
    assert action_insert_row_before(b, model)
    assert model.root_item.to_json() == {"a": 1, "new_key": None, "b": 2}

    a = model.index(0, 0, QModelIndex())
    assert action_insert_row_after(a, model)
    assert model.root_item.to_json() == {"a": 1, "new_key_2": None, "new_key": None, "b": 2}


def test_action_duplicate_preserves_subtree_and_renames_key(qtbot):
    model = JsonTreeModel({"obj": {"n": {"k": 1}}})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    obj = model.index(0, 0, QModelIndex())
    child = model.index(0, 0, obj)
    assert action_duplicate(view, child, model)

    assert model.get_item(obj).to_json() == {"n": {"k": 1}, "n_copy": {"k": 1}}


def test_move_up_down_reorders_siblings(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2, "c": 3})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    b = model.index(1, 0, QModelIndex())
    assert action_move_up(view, b, model)
    assert list(model.root_item.to_json().keys()) == ["b", "a", "c"]

    moved = model.index(0, 0, QModelIndex())
    assert action_move_down(view, moved, model)
    assert list(model.root_item.to_json().keys()) == ["a", "b", "c"]


def test_sort_keys_non_recursive_and_recursive(qtbot):
    model = JsonTreeModel({"root": {"z": 1, "a": {"y": 1, "b": 2}}})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    root = model.index(0, 0, QModelIndex())
    assert action_sort_keys(root, model, recursive=False)
    assert model.get_item(root).to_json() == {"a": {"y": 1, "b": 2}, "z": 1}

    assert action_sort_keys(root, model, recursive=True)
    assert model.get_item(root).to_json() == {"a": {"b": 2, "y": 1}, "z": 1}
