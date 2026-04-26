import pytest
from PySide6.QtCore import QEvent, QModelIndex, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QComboBox, QLineEdit, QStyleOptionViewItem, QWidget

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
    view_index = tab._source_to_view(name_index)
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
