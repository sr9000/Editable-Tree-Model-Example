from gmpy2 import mpq
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QStyleOptionViewItem

from delegates.number_affix_delegate import AffixCompositeEditor
from documents.tab import JsonTab
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix


def _value_index(tab: JsonTab):
    return tab.data_store.model.index(0, 2, QModelIndex())


def test_currency_affix_editor_commit(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "$", False, 1)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab._source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    tab.view_controller.value_delegate.setEditorData(editor, tab._source_to_view(index))

    editor.affix_combo.setCurrentText("$")
    editor.number_editor.setValue(1234)
    editor.space_button.setChecked(True)
    tab.view_controller.value_delegate.setModelData(editor, tab.data_store.model, tab._source_to_view(index))

    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.CURRENCY, "$", True, 1234)


def test_units_affix_editor_commit_float(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.UNITS, "%", False, mpq("1/2"))})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab._source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    tab.view_controller.value_delegate.setEditorData(editor, tab._source_to_view(index))

    editor.affix_combo.setCurrentText("%")
    editor.number_editor.setValue(mpq("1999/20"))
    editor.space_button.setChecked(False)
    tab.view_controller.value_delegate.setModelData(editor, tab.data_store.model, tab._source_to_view(index))

    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.UNITS, "%", False, mpq("1999/20"))


def test_invalid_affix_refuses_commit(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "$", False, 1)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    original = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex())).value

    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab._source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    editor.affix_combo.setCurrentText("")
    editor.number_editor.setValue(10)
    tab.view_controller.value_delegate.setModelData(editor, tab.data_store.model, tab._source_to_view(index))

    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert editor.property("invalid") is True
    assert item.value == original


def test_empty_affix_type_switch_paints_without_raising(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": 1234})
    qtbot.addWidget(tab)

    type_index = tab.data_store.model.index(0, 1, QModelIndex())
    assert tab.data_store.model.setData(type_index, JsonType.INTEGER_CURRENCY)

    option = QStyleOptionViewItem()
    tab.view_controller.value_delegate.initStyleOption(option, tab._source_to_view(_value_index(tab)))

    assert option.text == "1234"
