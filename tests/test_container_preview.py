from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QStyleOptionViewItem

from delegates.value import ValueDelegate
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
