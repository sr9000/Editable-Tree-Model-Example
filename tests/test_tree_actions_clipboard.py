import json

import gmpy2
from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtWidgets import QApplication, QTreeView

from tree.model import JsonTreeModel
from tree_actions.clipboard import MIME_JSON_TREE, copy_selection, copy_selection_value_only, copy_selection_with_name
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import cut_selection, delete_selection


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
    assert json.loads(md.text()) == {"a": 1}

    _select_rows(view, a, b)
    assert copy_selection(view)
    assert json.loads(QApplication.clipboard().text()) == {"a": 1, "b": 2}


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

    assert model.get_item(obj).to_json() == {"k": 1}


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


def test_copy_selection_with_mpq_float_values(qtbot):
    # Regression: copying float (mpq) values from inside an array used to crash with
    # "Type <class 'decimal.Decimal'> not serializable" because mpq_json_default
    # returned a Decimal that the stdlib json encoder could not handle.
    model = JsonTreeModel({"nums": [gmpy2.mpq("3.14"), gmpy2.mpq("1/2")]})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    nums = model.index(0, 0, QModelIndex())
    first = model.index(0, 0, nums)
    second = model.index(1, 0, nums)

    _select_rows(view, first, second)
    assert copy_selection(view)

    md = QApplication.clipboard().mimeData()
    assert md is not None
    assert md.hasFormat(MIME_JSON_TREE)
    parsed = json.loads(md.text())
    assert parsed == [3.14, 0.5]


def test_copy_paste_preserves_object_key_name_when_possible(qtbot):
    model = JsonTreeModel({"src": {"keep": 7}, "dst": {}})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    src = model.index(0, 0, QModelIndex())
    dst = model.index(1, 0, QModelIndex())
    keep = model.index(0, 0, src)

    _select_rows(view, keep)
    assert copy_selection(view)

    _select_rows(view, dst)
    assert paste_from_clipboard(view)

    assert model.get_item(dst).to_json() == {"keep": 7}


def test_copy_selection_with_name_and_value_only(qtbot):
    from tree_actions.clipboard import copy_selection_value_only, copy_selection_with_name

    model = JsonTreeModel({"foo": 42})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)
    foo = model.index(0, 0, QModelIndex())
    _select_rows(view, foo)
    assert copy_selection_with_name(view)
    md = QApplication.clipboard().mimeData()
    assert md.text() == '"foo": 42'
    assert md.hasFormat(MIME_JSON_TREE)
    assert copy_selection_value_only(view)
    md = QApplication.clipboard().mimeData()
    assert md.text() == "42"
    assert not md.hasFormat(MIME_JSON_TREE)


def test_copy_selection_string_value_is_json_quoted(qtbot):
    model = JsonTreeModel({"greeting": "hello world"})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    greet = model.index(0, 0, QModelIndex())
    _select_rows(view, greet)

    assert copy_selection_with_name(view)
    md = QApplication.clipboard().mimeData()
    assert md.text() == '"greeting": "hello world"'

    assert copy_selection_value_only(view)
    md = QApplication.clipboard().mimeData()
    assert md.text() == '"hello world"'


def test_copy_selection_object_array_includes_internal_values(qtbot):
    from tree_actions.clipboard import copy_selection_value_only, copy_selection_with_name

    model = JsonTreeModel({"foo": {"bar": [1, 2]}})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    foo = model.index(0, 0, QModelIndex())
    _select_rows(view, foo)

    assert copy_selection_with_name(view)
    md = QApplication.clipboard().mimeData()
    import json

    parsed = json.loads("{" + md.text() + "}")
    assert parsed == {"foo": {"bar": [1, 2]}}

    assert copy_selection_value_only(view)
    md = QApplication.clipboard().mimeData()
    parsed = json.loads(md.text())
    assert parsed == {"bar": [1, 2]}


def test_context_menu_column1_opens_type_editor_popup(qtbot, monkeypatch):
    from tree_actions.context_menu import show_context_menu

    model = JsonTreeModel({"foo": 42})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    import tree_actions.context_menu

    mock_index = model.index(0, 1, QModelIndex())
    monkeypatch.setattr(view, "indexAt", lambda pos: mock_index)

    edit_calls: list = []
    popup_called = {"value": False}

    monkeypatch.setattr(view, "edit", lambda idx: edit_calls.append(idx) or True)
    monkeypatch.setattr(
        tree_actions.context_menu,
        "_open_active_type_combo_popup",
        lambda _view: popup_called.__setitem__("value", True) or True,
    )

    class _ImmediateTimer:
        @staticmethod
        def singleShot(_ms, fn):
            fn()

    monkeypatch.setattr(tree_actions.context_menu, "QTimer", _ImmediateTimer)

    from PySide6.QtCore import QPoint

    show_context_menu(view, QPoint(0, 0))

    assert edit_calls
    assert edit_calls[0] == mock_index
    assert popup_called["value"]
