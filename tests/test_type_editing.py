import pytest
from gmpy2 import mpq
from PySide6.QtCore import QEvent, QModelIndex, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QComboBox, QLineEdit, QStyleOptionViewItem, QWidget

from delegates.type_delegate import JsonTypeDelegate
from documents.tab import JsonTab
from tree.codecs.bytes_codec import decode_bytes, encode_bytes
from tree.model import JsonTreeModel
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix


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

    assert model.data(child_name) == "#1"
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


def test_value_edit_only_switches_along_ascii_axis():
    """STRING <-> UNICODE switches automatically on the ascii axis.

    The cross-axis switch (single-line <-> multiline) is intentionally
    disabled: a UNICODE field stays single-line even if the user pastes
    multiline-unicode text — only the ascii axis flips automatically.
    """
    model = JsonTreeModel({"value": "hello"})
    value_index = model.index(0, 2, QModelIndex())

    # ASCII -> non-ASCII switches single-line STRING to UNICODE.
    assert model.setData(value_index, "caf\u00e9")
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.UNICODE

    # Multiline-unicode pasted into a single-line field stays UNICODE.
    assert model.setData(value_index, "line1\nline2\n\u03a9")
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.UNICODE

    # Going back to ASCII switches UNICODE -> STRING.
    assert model.setData(value_index, "back-to-ascii")
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.STRING


def test_value_edit_does_not_autopromote_string_to_bytes_like_type():
    model = JsonTreeModel({"value": "hello"})
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(value_index, "YWJjZGVmZ2hpamtsbW5vcA==")
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.STRING


def test_ascii_value_auto_downgrades_unicode_and_text_pseudotypes():
    model = JsonTreeModel({"value": "seed"})
    name_index = model.index(0, 0, QModelIndex())
    type_index = model.index(0, 1, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(type_index, JsonType.UNICODE)
    assert model.setData(value_index, "ascii only")
    item = model.get_item(name_index)
    assert item.json_type is JsonType.STRING

    assert model.setData(type_index, JsonType.TEXT)
    assert model.setData(value_index, "line1\nline2\nline3")
    item = model.get_item(name_index)
    assert item.json_type is JsonType.MULTILINE


def test_manual_type_change_auto_canonicalizes_text_pseudotypes_by_content():
    model = JsonTreeModel({"line": "ascii", "multi": "a\nb\nc", "u": "caf\u00e9", "t": "a\nb\n\u03a9"})

    line_type = model.index(0, 1, QModelIndex())
    multi_type = model.index(1, 1, QModelIndex())
    u_type = model.index(2, 1, QModelIndex())
    t_type = model.index(3, 1, QModelIndex())

    # ASCII content cannot stay in UNICODE/TEXT pseudo-types.
    assert model.setData(line_type, JsonType.UNICODE)
    assert model.get_item(model.index(0, 0, QModelIndex())).json_type is JsonType.STRING

    assert model.setData(multi_type, JsonType.TEXT)
    assert model.get_item(model.index(1, 0, QModelIndex())).json_type is JsonType.MULTILINE

    # Non-ASCII content canonicalizes to UNICODE/TEXT even when choosing base kinds.
    assert model.setData(u_type, JsonType.STRING)
    assert model.get_item(model.index(2, 0, QModelIndex())).json_type is JsonType.UNICODE

    assert model.setData(t_type, JsonType.MULTILINE)
    assert model.get_item(model.index(3, 0, QModelIndex())).json_type is JsonType.TEXT


def test_caps_lock_does_not_close_name_editor(qtbot):
    tab = JsonTab(lambda *_: None, data={"alpha": 1})
    qtbot.addWidget(tab)
    tab.show()

    name_index = tab.model.index(0, 0, QModelIndex())
    assert name_index.isValid()
    view_index = tab.view_controller.source_to_view(name_index)
    tab.view.setCurrentIndex(view_index)
    tab.view.edit(view_index)

    qtbot.waitUntil(lambda: tab.view.findChild(QLineEdit) is not None)
    editor = tab.view.findChild(QLineEdit)
    assert editor is not None

    # 1. A real CapsLock keypress must not close the editor.
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_CapsLock, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(editor, press)
    release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_CapsLock, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(editor, release)
    assert tab.view.state() == QAbstractItemView.State.EditingState

    # 2. A layout-switch-style FocusOut (xkb-bound CapsLock) must also be ignored.
    focus_out = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.ActiveWindowFocusReason)
    QApplication.sendEvent(editor, focus_out)
    assert tab.view.state() == QAbstractItemView.State.EditingState

    other_focus_out = QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason)
    QApplication.sendEvent(editor, other_focus_out)
    assert tab.view.state() == QAbstractItemView.State.EditingState


def test_enter_starts_editing_name_or_value(qtbot):
    tab = JsonTab(lambda *_: None, data={"alpha": "bravo"})
    qtbot.addWidget(tab)
    tab.show()

    source_name = tab.model.index(0, 0, QModelIndex())
    view_name = tab.view_controller.source_to_view(source_name)
    tab.view.setCurrentIndex(view_name)
    tab.view.setFocus()

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: tab.view.state() == QAbstractItemView.State.EditingState)
    assert tab.view.currentIndex().column() == 0


@pytest.mark.parametrize("enter_key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_enter_from_type_column_opens_type_combobox(qtbot, enter_key):
    tab = JsonTab(lambda *_: None, data={"alpha": "bravo"})
    qtbot.addWidget(tab)
    tab.show()

    source_type = tab.model.index(0, 1, QModelIndex())
    view_type = tab.view_controller.source_to_view(source_type)
    tab.view.setCurrentIndex(view_type)
    tab.view.setFocus()

    qtbot.keyClick(tab.view.viewport(), enter_key)

    qtbot.waitUntil(lambda: tab.view.state() == QAbstractItemView.State.EditingState)
    assert tab.view.currentIndex().column() == 1
    qtbot.waitUntil(lambda: tab.view.findChild(QComboBox) is not None)


def test_type_cell_icon_hidden_while_type_combobox_active(qtbot):
    tab = JsonTab(lambda *_: None, data={"alpha": "bravo"})
    qtbot.addWidget(tab)
    tab.show()

    source_type = tab.model.index(0, 1, QModelIndex())
    view_type = tab.view_controller.source_to_view(source_type)
    tab.view.setCurrentIndex(view_type)
    tab.view.edit(view_type)

    qtbot.waitUntil(lambda: tab.view.findChild(QComboBox) is not None)

    option = QStyleOptionViewItem()
    tab.view_controller.type_delegate.initStyleOption(option, view_type)
    assert option.icon.isNull()


def test_arrow_left_right_moves_between_columns(qtbot):
    tab = JsonTab(lambda *_: None, data={"alpha": "bravo"})
    qtbot.addWidget(tab)
    tab.show()

    source_name = tab.model.index(0, 0, QModelIndex())
    view_name = tab.view_controller.source_to_view(source_name)
    tab.view.setCurrentIndex(view_name)
    tab.view.setFocus()

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Right)
    assert tab.view.currentIndex().column() == 1

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Right)
    assert tab.view.currentIndex().column() == 2

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Left)
    assert tab.view.currentIndex().column() == 1


def test_arrow_up_down_moves_between_rows(qtbot):
    tab = JsonTab(lambda *_: None, data={"a": 1, "b": 2, "c": 3})
    qtbot.addWidget(tab)
    tab.show()

    source_mid_value = tab.model.index(1, 2, QModelIndex())
    view_mid_value = tab.view_controller.source_to_view(source_mid_value)
    tab.view.setCurrentIndex(view_mid_value)
    tab.view.setFocus()

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Down)
    assert tab.view.currentIndex().row() == 2
    assert tab.view.currentIndex().column() == 2

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Up)
    assert tab.view.currentIndex().row() == 1
    assert tab.view.currentIndex().column() == 2


def test_arrow_left_right_do_not_expand_or_collapse_rows(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"nested": 1}, "x": 2})
    qtbot.addWidget(tab)
    tab.show()

    source_obj_name = tab.model.index(0, 0, QModelIndex())
    view_obj_name = tab.view_controller.source_to_view(source_obj_name)
    tab.view.collapse(view_obj_name)
    assert not tab.view.isExpanded(view_obj_name)

    tab.view.setCurrentIndex(view_obj_name)
    tab.view.setFocus()

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Right)
    assert tab.view.currentIndex().column() == 1
    assert not tab.view.isExpanded(view_obj_name)

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Left)
    assert tab.view.currentIndex().column() == 0
    assert not tab.view.isExpanded(view_obj_name)


def test_space_toggles_expand_and_collapse_current_row(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"nested": 1}, "x": 2})
    qtbot.addWidget(tab)
    tab.show()

    source_obj_type = tab.model.index(0, 1, QModelIndex())
    view_obj_type = tab.view_controller.source_to_view(source_obj_type)
    view_obj_name = view_obj_type.siblingAtColumn(0)

    tab.view.collapse(view_obj_name)
    assert not tab.view.isExpanded(view_obj_name)

    tab.view.setCurrentIndex(view_obj_type)
    tab.view.setFocus()

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Space)
    assert tab.view.isExpanded(view_obj_name)

    qtbot.keyClick(tab.view.viewport(), Qt.Key.Key_Space)
    assert not tab.view.isExpanded(view_obj_name)


# All 16 text-family transitions: only STRING<->UNICODE and MULTILINE<->TEXT
# are allowed; cross-axis transitions must preserve the field's kind.
_FAM = (JsonType.STRING, JsonType.UNICODE, JsonType.MULTILINE, JsonType.TEXT)
_NON_ASCII = "caf\u00e9"
_ASCII_LINE = "hello"
_NON_ASCII_MULTI = "a\nb\n\u03a9"
_ASCII_MULTI = "a\nb\nc"


def _expected_after_edit(current: JsonType, value: str) -> JsonType:
    non_ascii = any(ord(ch) > 127 for ch in value)
    if current in (JsonType.MULTILINE, JsonType.TEXT):
        return JsonType.TEXT if non_ascii else JsonType.MULTILINE
    return JsonType.UNICODE if non_ascii else JsonType.STRING


@pytest.mark.parametrize("current", _FAM)
@pytest.mark.parametrize(
    "value",
    [_ASCII_LINE, _NON_ASCII, _ASCII_MULTI, _NON_ASCII_MULTI],
)
def test_text_family_only_switches_along_ascii_axis(current: JsonType, value: str):
    """Editing a value while the field is text-family stays in the same
    line/multiline shape; only the ascii axis can switch.
    """
    model = JsonTreeModel({"k": "seed"})
    name_idx = model.index(0, 0, QModelIndex())
    type_idx = model.index(0, 1, QModelIndex())
    value_idx = model.index(0, 2, QModelIndex())

    # Pin field to the desired text-family type, then unpin so the edit
    # path exercises the auto-typing branch (not the strict-coercion one).
    assert model.setData(type_idx, current)
    item = model.get_item(name_idx)
    item.explicit_type = False

    assert model.setData(value_idx, value)

    item = model.get_item(name_idx)
    assert item.json_type is _expected_after_edit(current, value)


def test_unicode_name_uses_italic_font_role():
    model = JsonTreeModel({"caf\u00e9": 1, "plain": 2})
    unicode_name = model.index(0, 0, QModelIndex())
    plain_name = model.index(1, 0, QModelIndex())

    unicode_font = model.data(unicode_name, Qt.ItemDataRole.FontRole)
    plain_font = model.data(plain_name, Qt.ItemDataRole.FontRole)

    assert unicode_font is not None
    assert unicode_font.italic()
    assert plain_font is None


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


# ---------------------------------------------------------------------------
# Phase-3 undo/redo regression tests
# ---------------------------------------------------------------------------


def test_bool_to_string_undo_redo(qtbot):
    tab = JsonTab(lambda *_: None, data={"flag": True})
    qtbot.addWidget(tab)
    type_idx = tab.model.index(0, 1, QModelIndex())

    tab.editing.commands.push_change_type(type_idx, JsonType.STRING)
    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == "true"

    tab.undo_stack.undo()
    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.BOOLEAN
    assert item.value is True

    tab.undo_stack.redo()
    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.value == "true"


def test_bytes_to_zlib_undo_redo(qtbot):
    raw = b"my lovely bytes! " * 5
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)
    tab = JsonTab(lambda *_: None, data={"blob": bytes_b64})
    qtbot.addWidget(tab)

    # The model infers BYTES type from the b64 string on load.
    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.BYTES

    type_idx = tab.model.index(0, 1, QModelIndex())
    tab.editing.commands.push_change_type(type_idx, JsonType.ZLIB)

    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.ZLIB
    assert decode_bytes(item.value, JsonType.ZLIB) == raw

    tab.undo_stack.undo()
    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.BYTES
    assert decode_bytes(item.value, JsonType.BYTES) == raw

    tab.undo_stack.redo()
    item = tab.model.get_item(tab.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.ZLIB
    assert decode_bytes(item.value, JsonType.ZLIB) == raw


def test_array_to_object_undo_redo(qtbot):
    tab = JsonTab(lambda *_: None, data={"arr": [1, 2, 3]})
    qtbot.addWidget(tab)

    arr_idx = tab.model.index(0, 0, QModelIndex())
    type_idx = tab.model.index(0, 1, QModelIndex())

    tab.editing.commands.push_change_type(type_idx, JsonType.OBJECT)
    item = tab.model.get_item(arr_idx)
    assert item.json_type is JsonType.OBJECT
    assert item.child_count() == 3
    assert [c.name for c in item.child_items] == ["item1", "item2", "item3"]

    tab.undo_stack.undo()
    item = tab.model.get_item(arr_idx)
    assert item.json_type is JsonType.ARRAY
    assert item.child_count() == 3
    assert all(c.name is None for c in item.child_items)
    assert [c.value for c in item.child_items] == [1, 2, 3]

    tab.undo_stack.redo()
    item = tab.model.get_item(arr_idx)
    assert item.json_type is JsonType.OBJECT
    assert [c.name for c in item.child_items] == ["item1", "item2", "item3"]


def test_integer_to_integer_currency_creates_affix_wrapper():
    model = JsonTreeModel({"v": 1234})
    type_idx = model.index(0, 1, QModelIndex())
    assert model.setData(type_idx, JsonType.INTEGER_CURRENCY)
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.CURRENCY, "", False, 1234)


@pytest.mark.parametrize(
    ("target_type", "expected_kind", "expected_number_type"),
    [
        (JsonType.INTEGER_CURRENCY, AffixKind.CURRENCY, int),
        (JsonType.INTEGER_UNITS, AffixKind.UNITS, int),
        (JsonType.FLOAT_CURRENCY, AffixKind.CURRENCY, mpq),
        (JsonType.FLOAT_UNITS, AffixKind.UNITS, mpq),
    ],
)
def test_null_to_affix_type_creates_transitional_affix_wrapper(target_type, expected_kind, expected_number_type):
    model = JsonTreeModel({"v": None})
    type_idx = model.index(0, 1, QModelIndex())

    assert model.setData(type_idx, target_type)

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is target_type
    assert isinstance(item.value, NumberAffix)
    assert item.value.kind is expected_kind
    assert item.value.affix == ""
    assert item.value.space is False
    assert isinstance(item.value.number, expected_number_type)


def test_float_currency_to_integer_currency_requires_exact_integer():
    model = JsonTreeModel({"v": NumberAffix(AffixKind.CURRENCY, "$", False, 3.5)})
    type_idx = model.index(0, 1, QModelIndex())
    assert model.setData(type_idx, JsonType.FLOAT_CURRENCY)
    assert model.setData(type_idx, JsonType.INTEGER_CURRENCY)


def test_float_currency_to_integer_currency_exact_value_succeeds():
    model = JsonTreeModel({"v": NumberAffix(AffixKind.CURRENCY, "$", False, 3.0)})
    type_idx = model.index(0, 1, QModelIndex())
    assert model.setData(type_idx, JsonType.FLOAT_CURRENCY)
    assert model.setData(type_idx, JsonType.INTEGER_CURRENCY)
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.CURRENCY, "$", False, 3)


def test_integer_currency_to_integer_units_flips_kind_preserving_payload():
    model = JsonTreeModel({"v": NumberAffix(AffixKind.CURRENCY, "$", True, 42)})
    type_idx = model.index(0, 1, QModelIndex())
    assert model.setData(type_idx, JsonType.INTEGER_CURRENCY)
    assert model.setData(type_idx, JsonType.INTEGER_UNITS)
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.value == NumberAffix(AffixKind.UNITS, "$", True, 42)


@pytest.mark.parametrize(
    ("original", "string_type", "target_type"),
    [
        (
            NumberAffix(AffixKind.CURRENCY, "lvl", True, 7, 4, -1, True),
            JsonType.STRING,
            JsonType.INTEGER_CURRENCY,
        ),
        (
            NumberAffix(AffixKind.CURRENCY, "lvl", True, mpq("3/2"), 4, 3, True),
            JsonType.STRING,
            JsonType.FLOAT_CURRENCY,
        ),
        (
            NumberAffix(AffixKind.UNITS, "kg", False, 12, 3, -1, False),
            JsonType.STRING,
            JsonType.INTEGER_UNITS,
        ),
        (
            NumberAffix(AffixKind.UNITS, "%", False, mpq("1999/20"), 0, 3, False),
            JsonType.STRING,
            JsonType.FLOAT_UNITS,
        ),
    ],
    ids=["int-currency", "float-currency", "int-units", "float-units"],
)
def test_type_switch_string_round_trip_preserves_affix_metadata(original, string_type, target_type):
    model = JsonTreeModel({"v": original})
    type_idx = model.index(0, 1, QModelIndex())

    assert model.setData(type_idx, string_type)
    assert model.setData(type_idx, target_type)

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.value == original
