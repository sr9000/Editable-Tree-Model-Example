from gmpy2 import mpq
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QStyleOptionViewItem

from delegates.value import ValueDelegate
from tree.model import JsonTreeModel
from tree.model_roles import JSON_TYPE_ROLE
from tree.types import JsonType


def test_edit_role_returns_raw_values_for_mpq_none_and_bool():
    model = JsonTreeModel({"ratio": mpq("1/2"), "nothing": None, "flag": True})

    ratio_value = model.index(0, 2, QModelIndex())
    none_value = model.index(1, 2, QModelIndex())
    bool_value = model.index(2, 2, QModelIndex())

    assert isinstance(model.data(ratio_value, Qt.ItemDataRole.EditRole), mpq)
    assert model.data(ratio_value, Qt.ItemDataRole.EditRole) == mpq("1/2")
    assert model.data(none_value, Qt.ItemDataRole.EditRole) is None
    assert model.data(bool_value, Qt.ItemDataRole.EditRole) is True


def test_tooltip_role_caps_long_text_to_4kb_plus_ellipsis():
    model = JsonTreeModel({"long": "x" * 5000})
    value_index = model.index(0, 2, QModelIndex())

    tooltip = model.data(value_index, Qt.ItemDataRole.ToolTipRole)

    assert isinstance(tooltip, str)
    assert len(tooltip) == 4097
    assert tooltip.endswith("…")


def test_json_type_role_is_exposed_for_value_column():
    model = JsonTreeModel({"ratio": mpq("1/2")})
    value_index = model.index(0, 2, QModelIndex())

    assert model.data(value_index, JSON_TYPE_ROLE) is JsonType.PERCENT


def test_value_delegate_formats_percent_with_suffix():
    model = JsonTreeModel({"ratio": mpq("1/2")})
    value_index = model.index(0, 2, QModelIndex())
    delegate = ValueDelegate()
    option = QStyleOptionViewItem()

    delegate.initStyleOption(option, value_index)

    assert option.text == "50%"


def test_value_delegate_formats_binary_cells_as_size():
    model = JsonTreeModel({"blob": "dGVzdA=="})
    type_index = model.index(0, 1, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())
    assert model.setData(type_index, JsonType.BYTES, Qt.ItemDataRole.EditRole)

    delegate = ValueDelegate()
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, value_index)

    assert option.text == "<4 byte>"


def test_value_delegate_elides_long_text_values():
    model = JsonTreeModel({"text": "a" * 120})
    type_index = model.index(0, 1, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())
    assert model.setData(type_index, JsonType.STRING, Qt.ItemDataRole.EditRole)

    delegate = ValueDelegate()
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, value_index)

    assert len(option.text) == 81
    assert option.text.endswith("…")
