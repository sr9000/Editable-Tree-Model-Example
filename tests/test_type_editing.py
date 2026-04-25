from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QStyleOptionViewItem, QWidget

from delegate import JsonTypeDelegate
from enums import JsonType
from json_tab import JsonTab
from tree_model import JsonTreeModel


def test_name_editing_object_and_duplicate_rejection():
    model = JsonTreeModel({"a": 1, "b": 2})

    a_name = model.index(0, 0, QModelIndex())
    b_name = model.index(1, 0, QModelIndex())

    assert model.setData(a_name, "alpha")
    assert not model.setData(b_name, "alpha")
    assert model.root_item.to_json() == {"alpha": 1, "b": 2}


def test_array_name_column_shows_index_and_is_read_only():
    model = JsonTreeModel({"arr": [1, 2]})
    arr_index = model.index(0, 0, QModelIndex())
    child_name = model.index(0, 0, arr_index)

    assert model.data(child_name) == "0"
    assert not (model.flags(child_name) & Qt.ItemFlag.ItemIsEditable)
    assert not model.setData(child_name, "renamed")


def test_type_change_sets_explicit_type_and_coerces_value():
    model = JsonTreeModel({"value": "42"})
    type_index = model.index(0, 1, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(type_index, JsonType.INTEGER)

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.explicit_type is True
    assert item.json_type is JsonType.INTEGER
    assert item.value == 42

    # Explicit INTEGER typing rejects incompatible value text
    assert not model.setData(value_index, "not-an-int")
    assert item.value == 42


def test_type_pinning_keeps_string_for_base64_like_value():
    model = JsonTreeModel({"value": "hello"})
    type_index = model.index(0, 1, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(type_index, JsonType.STRING)
    assert model.setData(value_index, "YWJjZGVmZ2hpamtsbW5vcA==")

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.explicit_type is True
    assert item.json_type is JsonType.STRING


def test_json_type_delegate_preselects_and_commits(qtbot):
    model = JsonTreeModel({"value": 1})
    type_index = model.index(0, 1, QModelIndex())

    delegate = JsonTypeDelegate()
    parent = QWidget()
    qtbot.addWidget(parent)

    editor = delegate.createEditor(parent, QStyleOptionViewItem(), type_index)
    assert isinstance(editor, QComboBox)
    delegate.setEditorData(editor, type_index)

    assert editor.currentData() == JsonType.INTEGER

    target = editor.findData(JsonType.BOOLEAN)
    editor.setCurrentIndex(target)
    delegate.setModelData(editor, model, type_index)

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.BOOLEAN
