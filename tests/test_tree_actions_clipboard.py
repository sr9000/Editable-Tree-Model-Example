import json

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QApplication, QTreeView

from tree_model import JsonTreeModel
from tree_view import MIME_JSON_TREE, copy_selection, cut_selection, delete_selection, paste_from_clipboard


def _select_rows(view: QTreeView, *indexes) -> None:
    sm = view.selectionModel()
    first, *rest = indexes
    sm.select(first, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    sm.setCurrentIndex(first, QItemSelectionModel.SelectionFlag.NoUpdate)
    for idx in rest:
        sm.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


def test_copy_selection_single_and_multi(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    a = model.index(0, 0, QModelIndex())
    b = model.index(1, 0, QModelIndex())

    _select_rows(view, a)
    assert copy_selection(view)

    md = QApplication.clipboard().mimeData()
    assert md is not None
    assert md.hasFormat(MIME_JSON_TREE)
    assert json.loads(md.text()) == 1

    _select_rows(view, a, b)
    assert copy_selection(view)
    assert json.loads(QApplication.clipboard().text()) == [1, 2]


def test_cut_and_delete_selection_remove_rows(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2, "c": 3})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    b = model.index(1, 0, QModelIndex())
    _select_rows(view, b)
    assert cut_selection(view)
    assert model.root_item.to_json() == {"a": 1, "c": 3}

    a = model.index(0, 0, QModelIndex())
    c = model.index(1, 0, QModelIndex())
    _select_rows(view, a, c)
    assert delete_selection(view)
    assert model.root_item.to_json() == {}


def test_paste_into_object_inserts_children(qtbot):
    model = JsonTreeModel({"obj": {}})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    obj = model.index(0, 0, QModelIndex())
    _select_rows(view, obj)

    QApplication.clipboard().setText('{"k": 1}')
    assert paste_from_clipboard(view)

    pasted = model.get_item(model.index(0, 0, obj))
    assert pasted.json_type.value == "object"
    assert pasted.to_json() == {"k": 1}


def test_paste_into_primitive_inserts_sibling_after(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    a = model.index(0, 0, QModelIndex())
    _select_rows(view, a)

    QApplication.clipboard().setText("3")
    assert paste_from_clipboard(view)

    assert model.root_item.to_json() == {"a": 1, "new_key": 3, "b": 2}
