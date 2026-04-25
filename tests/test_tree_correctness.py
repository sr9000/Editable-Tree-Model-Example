import gmpy2
import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTreeView

from enums import JsonType, parse_json_type
from model_actions import action_insert_child
from tree_item import JsonTreeItem
from tree_model import JsonTreeModel


def test_insert_row_under_object_creates_unique_named_null_children():
    model = JsonTreeModel({"a": 1})

    assert model.insertRow(model.rowCount(), QModelIndex())
    first = model.get_item(model.index(1, 0, QModelIndex()))
    assert first.name == "new_key"
    assert first.json_type is JsonType.NULL
    assert first.value is None

    assert model.insertRow(model.rowCount(), QModelIndex())
    second = model.get_item(model.index(2, 0, QModelIndex()))
    assert second.name == "new_key_2"
    assert second.json_type is JsonType.NULL

    assert model.root_item.to_json() == {"a": 1, "new_key": None, "new_key_2": None}


def test_insert_row_under_array_keeps_name_none():
    model = JsonTreeModel({"arr": [1]})
    arr_index = model.index(0, 0, QModelIndex())

    assert model.insertRow(1, arr_index)

    inserted = model.get_item(model.index(1, 0, arr_index))
    assert inserted.name is None
    assert inserted.json_type is JsonType.NULL


def test_set_data_recomputes_json_type():
    model = JsonTreeModel({"a": 1})
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(value_index, "hello")

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.STRING


def test_to_json_raises_for_unnamed_object_child():
    root = JsonTreeItem(None, {})
    root.child_items.append(JsonTreeItem(root, 1, None))

    with pytest.raises(ValueError, match="OBJECT child has no name"):
        root.to_json()


def test_parse_json_type_is_total_and_has_narrower_heuristics():
    # Floats / mpq in [0, 1] are PERCENT; integers 0/1 stay INTEGER.
    assert parse_json_type(0) is JsonType.INTEGER
    assert parse_json_type(1) is JsonType.INTEGER
    assert parse_json_type(0.5) is JsonType.PERCENT
    assert parse_json_type(0.0) is JsonType.PERCENT
    assert parse_json_type(1.0) is JsonType.PERCENT
    assert parse_json_type(1.5) is JsonType.FLOAT
    assert parse_json_type(-0.1) is JsonType.FLOAT
    assert parse_json_type(gmpy2.mpq("50/100")) is JsonType.PERCENT
    assert parse_json_type(gmpy2.mpq("1/2")) is JsonType.PERCENT
    assert parse_json_type(gmpy2.mpq("3/2")) is JsonType.FLOAT

    # A pure base64 string (regex + padding + clean decode) is BYTES.
    assert parse_json_type("abcd") is JsonType.BYTES
    # Strings that aren't valid base64 stay STRING.
    assert parse_json_type("hi\n") is JsonType.STRING
    assert parse_json_type("hello") is JsonType.STRING
    assert parse_json_type((1, 2)) is JsonType.STRING

    unknown = JsonTreeItem(None, (1, 2), "tuple_value")
    assert unknown.value == "(1, 2)"


def test_flags_are_safe_for_malformed_binary_payloads():
    model = JsonTreeModel({"blob": "dGVzdA=="})
    name_index = model.index(0, 0, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())

    item = model.get_item(name_index)
    item.json_type = JsonType.BYTES
    item.value = "not-base64"
    item.editable = item._compute_editable()

    flags = model.flags(value_index)
    assert (flags & Qt.ItemFlag.ItemIsEditable) == Qt.ItemFlag.NoItemFlags


def test_column_api_returns_false_without_changing_model():
    model = JsonTreeModel({"a": 1})
    assert model.columnCount() == 3

    assert model.insertColumn(1) is False
    assert model.removeColumn(1) is False

    assert model.columnCount() == 3


def test_action_insert_child_main_path(qtbot):
    model = JsonTreeModel({"obj": {"existing": 1}})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    obj_index = model.index(0, 0, QModelIndex())
    assert obj_index.isValid()

    assert action_insert_child(view, obj_index, model)

    inserted = model.get_item(model.index(0, 0, obj_index))
    assert inserted.name == "new_key"
    assert inserted.json_type is JsonType.NULL
    assert model.get_item(obj_index).to_json() == {"new_key": None, "existing": 1}


def test_action_insert_child_rejects_non_container_parent(qtbot):
    model = JsonTreeModel({"leaf": 1})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)

    leaf_index = model.index(0, 0, QModelIndex())
    assert leaf_index.isValid()

    assert not action_insert_child(view, leaf_index, model)
    assert model.root_item.to_json() == {"leaf": 1}
