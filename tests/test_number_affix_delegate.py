from gmpy2 import mpq
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QStyleOptionViewItem

from documents.tab import JsonTab
from editors.inline.affix_composite import AffixCompositeEditor
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix


def _value_index(tab: JsonTab):
    return tab.model.index(0, 2, QModelIndex())


def test_currency_affix_editor_commit(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "$", False, 1)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab.view_controller.source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    tab.view_controller.value_delegate.setEditorData(editor, tab.view_controller.source_to_view(index))

    editor.affix_combo.setCurrentText("$")
    qtbot.mouseClick(editor.width_button, Qt.MouseButton.LeftButton)
    editor.width_spinbox.setValue(4)
    editor.number_editor.setValue(12)
    editor.space_button.setChecked(True)
    tab.view_controller.value_delegate.setModelData(editor, tab.model, tab.view_controller.source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.CURRENCY, "$", True, 12, 4, -1)


def test_currency_affix_editor_commit_with_explicit_plus(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "pepe", False, 7)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab.view_controller.source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    tab.view_controller.value_delegate.setEditorData(editor, tab.view_controller.source_to_view(index))

    editor.affix_combo.setCurrentText("pepe")
    qtbot.mouseClick(editor.plus_button, Qt.MouseButton.LeftButton)
    editor.number_editor.setValue(777)
    tab.view_controller.value_delegate.setModelData(editor, tab.model, tab.view_controller.source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.CURRENCY, "pepe", False, 777, 0, -1, True)


def test_units_affix_editor_commit_float(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.UNITS, "%", False, mpq("1/2"))})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab.view_controller.source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    tab.view_controller.value_delegate.setEditorData(editor, tab.view_controller.source_to_view(index))

    editor.affix_combo.setCurrentText("%")
    assert editor.precision_button is not None
    assert editor.precision_spinbox is not None
    qtbot.mouseClick(editor.precision_button, Qt.MouseButton.LeftButton)
    editor.precision_spinbox.setValue(3)
    editor.number_editor.setValue(mpq("1999/20"))
    editor.space_button.setChecked(False)
    tab.view_controller.value_delegate.setModelData(editor, tab.model, tab.view_controller.source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.UNITS, "%", False, mpq("1999/20"), 0, 3)


def test_integer_affix_editor_shows_width_spinbox_and_builds_selected_width(qtbot):
    editor = AffixCompositeEditor(
        None,
        kind=AffixKind.CURRENCY,
        is_integer=True,
        mru_items=["abc-"],
    )
    qtbot.addWidget(editor)
    editor.show()

    editor.set_value(NumberAffix(AffixKind.CURRENCY, "abc-", False, 1, 3, -1))

    assert editor.width_button.isChecked()
    assert not editor.width_spinbox.isHidden()
    assert editor.width_spinbox.value() == 3

    qtbot.mouseClick(editor.width_button, Qt.MouseButton.LeftButton)
    assert editor.width_spinbox.isHidden()

    qtbot.mouseClick(editor.width_button, Qt.MouseButton.LeftButton)
    editor.number_editor.setValue(12)
    editor.width_spinbox.setValue(5)

    built = editor.build_value()
    assert built == NumberAffix(AffixKind.CURRENCY, "abc-", False, 12, 5, -1)


def test_affix_editor_plus_toggle_round_trips_explicit_positive_sign(qtbot):
    editor = AffixCompositeEditor(
        None,
        kind=AffixKind.CURRENCY,
        is_integer=True,
        mru_items=["pepe"],
    )
    qtbot.addWidget(editor)
    editor.show()

    editor.set_value(NumberAffix(AffixKind.CURRENCY, "pepe", False, 777, 0, -1, True))

    assert editor.plus_button.isChecked()
    assert editor.plus_button.text() == "Plus"

    qtbot.mouseClick(editor.plus_button, Qt.MouseButton.LeftButton)
    assert editor.build_value() == NumberAffix(AffixKind.CURRENCY, "pepe", False, 777)

    qtbot.mouseClick(editor.plus_button, Qt.MouseButton.LeftButton)
    assert editor.build_value() == NumberAffix(AffixKind.CURRENCY, "pepe", False, 777, 0, -1, True)


def test_float_affix_editor_shows_precision_spinbox_and_updates_step(qtbot):
    editor = AffixCompositeEditor(
        None,
        kind=AffixKind.UNITS,
        is_integer=False,
        mru_items=["%"],
    )
    qtbot.addWidget(editor)
    editor.show()

    editor.set_value(NumberAffix(AffixKind.UNITS, "%", False, mpq("15432/1250"), 0, 6))

    assert editor.precision_button is not None
    assert editor.precision_spinbox is not None
    assert editor.precision_button.isChecked()
    assert not editor.precision_spinbox.isHidden()
    assert editor.precision_spinbox.value() == 6
    assert editor.number_editor.singleStep() == mpq(1, 10**6)

    editor.precision_spinbox.setValue(3)

    built = editor.build_value()
    assert editor.number_editor.singleStep() == mpq(1, 1000)
    assert built == NumberAffix(AffixKind.UNITS, "%", False, mpq("15432/1250"), 0, 3)


def test_invalid_affix_refuses_commit(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": NumberAffix(AffixKind.CURRENCY, "$", False, 1)})
    qtbot.addWidget(tab)

    index = _value_index(tab)
    original = tab.model.get_item(tab.model.index(0, 0, QModelIndex())).value

    editor = tab.view_controller.value_delegate.createEditor(
        tab.view, QStyleOptionViewItem(), tab.view_controller.source_to_view(index)
    )
    assert isinstance(editor, AffixCompositeEditor)
    editor.affix_combo.setCurrentText("")
    editor.number_editor.setValue(10)
    tab.view_controller.value_delegate.setModelData(editor, tab.model, tab.view_controller.source_to_view(index))

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert editor.property("invalid") is True
    assert item.value == original


def test_empty_affix_type_switch_paints_without_raising(qtbot):
    tab = JsonTab(lambda *_: None, data={"v": 1234})
    qtbot.addWidget(tab)

    type_index = tab.model.index(0, 1, QModelIndex())
    assert tab.model.setData(type_index, JsonType.INTEGER_CURRENCY)

    option = QStyleOptionViewItem()
    tab.view_controller.value_delegate.initStyleOption(option, tab.view_controller.source_to_view(_value_index(tab)))

    assert option.text == "1234"
