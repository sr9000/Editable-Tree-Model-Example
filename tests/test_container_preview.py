from gmpy2 import mpq
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QStyleOptionViewItem

from delegates.value import ValueDelegate
from documents.tab import JsonTab
from tree.model import JsonTreeModel


def _value_text(model: JsonTreeModel, row: int) -> str:
    delegate = ValueDelegate()
    option = QStyleOptionViewItem()
    value_index = model.index(row, 2, QModelIndex())
    delegate.initStyleOption(option, value_index)
    return option.text


def test_empty_array_preview_shows_item_count():
    model = JsonTreeModel({"arr": []})

    assert _value_text(model, 0) == "[0 items]"


def test_array_preview_shows_count_and_values():
    model = JsonTreeModel({"arr": [1, 2, 3]})

    assert _value_text(model, 0) == "[3 items]  1, 2, 3"


def test_object_preview_shows_count_and_key_value_pairs():
    model = JsonTreeModel({"obj": {"a": 1, "b": True, "c": "x"}})

    assert _value_text(model, 0) == "{3 keys}  a: 1, b: true, c: x"


def test_container_preview_is_elided_to_80_chars():
    model = JsonTreeModel({"arr": ["x" * 60, "y" * 60, "z" * 60]})

    text = _value_text(model, 0)
    assert len(text) == 80
    assert text.endswith("…")


def test_multiline_values_use_single_line_separator_in_container_preview():
    model = JsonTreeModel({"arr": ["line1\nline2", "tail"]})

    assert _value_text(model, 0) == "[2 items]  line1 | line2, tail"


def test_container_preview_works_through_tab_proxy(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"a": 1}, "arr": [1, 2]}, show_root=False)
    qtbot.addWidget(tab)

    obj_value = tab.proxy.index(0, 2, QModelIndex())
    arr_value = tab.proxy.index(1, 2, QModelIndex())
    option = QStyleOptionViewItem()

    tab.value_delegate.initStyleOption(option, obj_value)
    assert option.text == "{1 key}  a: 1"

    tab.value_delegate.initStyleOption(option, arr_value)
    assert option.text == "[2 items]  1, 2"


def test_container_preview_hidden_when_expanded_shows_meta_only(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"a": 1}, "arr": [1, 2]}, show_root=False)
    qtbot.addWidget(tab)

    obj_name = tab.proxy.index(0, 0, QModelIndex())
    arr_name = tab.proxy.index(1, 0, QModelIndex())
    tab.view.expand(obj_name)
    tab.view.expand(arr_name)

    obj_value = tab.proxy.index(0, 2, QModelIndex())
    arr_value = tab.proxy.index(1, 2, QModelIndex())
    option = QStyleOptionViewItem()
    option.widget = tab.view

    tab.value_delegate.initStyleOption(option, obj_value)
    assert option.text == "{1 key}"

    tab.value_delegate.initStyleOption(option, arr_value)
    assert option.text == "[2 items]"


def test_percent_formatting_works_through_tab_proxy(qtbot):
    tab = JsonTab(lambda *_: None, data={"ratio": mpq("1/2")}, show_root=False)
    qtbot.addWidget(tab)

    ratio_value = tab.proxy.index(0, 2, QModelIndex())
    option = QStyleOptionViewItem()
    tab.value_delegate.initStyleOption(option, ratio_value)

    assert option.text == "50%"
