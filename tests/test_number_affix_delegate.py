from gmpy2 import mpq
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QStyleOptionViewItem

from delegates.number_affix_delegate import AffixCompositeEditor
from documents.tab import JsonTab
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix


def _value_index(tab: JsonTab):
    return tab.model.index(0, 2, QModelIndex())


def test_currency_affix_editor_commit(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "$", False, 1)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.value_delegate.createEditor(tab.view, QStyleOptionViewItem(), tab._source_to_view(index))
    assert isinstance(editor, AffixCompositeEditor)
    tab.value_delegate.setEditorData(editor, tab._source_to_view(index))

    editor.affix_combo.setCurrentText("$")
    editor.number_editor.setValue(1234)
    editor.space_button.setChecked(True)
    tab.value_delegate.setModelData(editor, tab.model, tab._source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.CURRENCY, "$", True, 1234)


def test_units_affix_editor_commit_float(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.UNITS, "%", False, mpq("1/2"))})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.value_delegate.createEditor(tab.view, QStyleOptionViewItem(), tab._source_to_view(index))
    assert isinstance(editor, AffixCompositeEditor)
    tab.value_delegate.setEditorData(editor, tab._source_to_view(index))

    editor.affix_combo.setCurrentText("%")
    editor.number_editor.setValue(mpq("1999/20"))
    editor.space_button.setChecked(False)
    tab.value_delegate.setModelData(editor, tab.model, tab._source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.UNITS, "%", False, mpq("1999/20"))


def test_invalid_affix_refuses_commit(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "$", False, 1)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    original = tab.model.get_item(tab.model.index(0, 0, QModelIndex())).value

    editor = tab.value_delegate.createEditor(tab.view, QStyleOptionViewItem(), tab._source_to_view(index))
    assert isinstance(editor, AffixCompositeEditor)
    editor.affix_combo.setCurrentText("")
    editor.number_editor.setValue(10)
    tab.value_delegate.setModelData(editor, tab.model, tab._source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert editor.property("invalid") is True
    assert item.value == original
