"""Tests for YAML clipboard interop, configurable copy format, and New From Clipboard."""

from __future__ import annotations

import json

import pytest
import yaml
from PySide6.QtCore import QMimeData, QModelIndex
from PySide6.QtWidgets import QApplication, QTreeView

from app.main_window import MainWindow
from core.raw_numeric import REASON_OVERFLOW, REASON_UNDERFLOW, RawNumericValue
from documents.tab import JsonTab
from state.clipboard_settings import (
    CLIPBOARD_TEXT_FORMAT_JSON,
    CLIPBOARD_TEXT_FORMAT_YAML,
    get_clipboard_text_format,
    set_clipboard_text_format,
)
from tree.model import JsonTreeModel
from tree.types import JsonType
from tree_actions.clipboard import (
    MIME_JSON_TREE,
    clipboard_text_is_valid_data,
    clipboard_to_tab_data,
    copy_selection,
    entries_from_mime,
)
from tree_actions.paste import paste_from_clipboard

_EXTREME_FLOATS_JSON = (
    '{"underfloat": 31e-327018450730, ' '"overfloat": 31e+327018450730, ' '"untouchable": "$ 31e-327018450730"}'
)


def _current_tab(win: MainWindow) -> JsonTab:
    tab = win._current_tab()
    assert isinstance(tab, JsonTab)
    return tab


def _set_clipboard_text(text: str) -> None:
    QApplication.clipboard().setText(text)


def _reset_format():
    set_clipboard_text_format(CLIPBOARD_TEXT_FORMAT_JSON)


def _find_named_item(root, name: str):
    for child in root.child_items:
        if child.name == name:
            return child
        found = _find_named_item(child, name)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# entries_from_mime — YAML fallback
# ---------------------------------------------------------------------------


def test_entries_from_mime_accepts_yaml_mapping(qtbot):
    mime = QMimeData()
    mime.setText("key1: alpha\nkey2: beta\n")
    result = entries_from_mime(mime)
    assert result is not None
    data = {e["name"]: e["value"] for e in result}
    assert data == {"key1": "alpha", "key2": "beta"}


def test_entries_from_mime_accepts_yaml_list(qtbot):
    mime = QMimeData()
    mime.setText("- 1\n- 2\n- 3\n")
    result = entries_from_mime(mime)
    assert result is not None
    assert [e["value"] for e in result] == [1, 2, 3]


def test_entries_from_mime_rejects_bare_yaml_scalar(qtbot):
    """Plain text that is valid YAML but not a dict/list must be rejected."""
    mime = QMimeData()
    mime.setText("this is not json nor a mapping")
    assert entries_from_mime(mime) is None


def test_entries_from_mime_json_takes_priority_over_yaml(qtbot):
    """Internal app MIME must still be preferred over plain text."""
    from tree_actions.clipboard import MIME_JSON_TREE

    entries = [{"name": "x", "value": 42}]
    inner = json.dumps({"entries": entries})
    mime = QMimeData()
    mime.setData(MIME_JSON_TREE, inner.encode())
    mime.setText("y: 99")  # Would parse as YAML
    result = entries_from_mime(mime)
    assert result is not None
    assert result[0]["name"] == "x"
    assert result[0]["value"] == 42


def test_entries_from_mime_preserves_extreme_json_numbers_as_raw_numeric(qtbot):
    mime = QMimeData()
    mime.setText(_EXTREME_FLOATS_JSON)

    result = entries_from_mime(mime)

    assert result is not None
    data = {e["name"]: e["value"] for e in result}
    assert isinstance(data["underfloat"], RawNumericValue)
    assert data["underfloat"].raw == "31e-327018450730"
    assert data["underfloat"].reason == REASON_UNDERFLOW
    assert isinstance(data["overfloat"], RawNumericValue)
    assert data["overfloat"].raw == "31e+327018450730"
    assert data["overfloat"].reason == REASON_OVERFLOW
    assert data["untouchable"] == "$ 31e-327018450730"


# ---------------------------------------------------------------------------
# clipboard_text_is_valid_data
# ---------------------------------------------------------------------------


def test_clipboard_valid_json(qtbot):
    _set_clipboard_text('{"a": 1}')
    assert clipboard_text_is_valid_data()


def test_clipboard_valid_yaml(qtbot):
    _set_clipboard_text("a: 1\nb: 2\n")
    assert clipboard_text_is_valid_data()


def test_clipboard_invalid(qtbot):
    _set_clipboard_text("not valid json or structured yaml")
    assert not clipboard_text_is_valid_data()


def test_clipboard_empty(qtbot):
    _set_clipboard_text("")
    assert not clipboard_text_is_valid_data()


# ---------------------------------------------------------------------------
# clipboard_to_tab_data
# ---------------------------------------------------------------------------


def test_clipboard_to_tab_data_json(qtbot):
    from io_formats.detect import SAVE_FORMAT_JSON

    _set_clipboard_text('{"foo": "bar"}')
    data, fmt = clipboard_to_tab_data()
    assert data == {"foo": "bar"}
    assert fmt == SAVE_FORMAT_JSON


def test_clipboard_to_tab_data_json_preserves_extreme_floats(qtbot):
    from io_formats.detect import SAVE_FORMAT_JSON

    _set_clipboard_text(_EXTREME_FLOATS_JSON)

    data, fmt = clipboard_to_tab_data()

    assert fmt == SAVE_FORMAT_JSON
    assert isinstance(data["underfloat"], RawNumericValue)
    assert data["underfloat"].raw == "31e-327018450730"
    assert data["underfloat"].reason == REASON_UNDERFLOW
    assert isinstance(data["overfloat"], RawNumericValue)
    assert data["overfloat"].raw == "31e+327018450730"
    assert data["overfloat"].reason == REASON_OVERFLOW
    assert data["untouchable"] == "$ 31e-327018450730"


def test_clipboard_to_tab_data_yaml(qtbot):
    from io_formats.detect import SAVE_FORMAT_YAML

    _set_clipboard_text("foo: bar\nbaz: 1\n")
    data, fmt = clipboard_to_tab_data()
    assert data == {"foo": "bar", "baz": 1}
    assert fmt == SAVE_FORMAT_YAML


def test_clipboard_to_tab_data_yaml_multidoc(qtbot):
    from io_formats.detect import SAVE_FORMAT_YAML_MULTI

    _set_clipboard_text("---\nfoo: 1\n---\nbar: 2\n")
    data, fmt = clipboard_to_tab_data()
    assert isinstance(data, list)
    assert len(data) == 2
    assert fmt == SAVE_FORMAT_YAML_MULTI


def test_clipboard_to_tab_data_invalid(qtbot):
    _set_clipboard_text("not parseable")
    data, fmt = clipboard_to_tab_data()
    assert data is None
    assert fmt is None


# ---------------------------------------------------------------------------
# Configurable copy text format
# ---------------------------------------------------------------------------


def test_copy_format_default_is_json(qtbot):
    _reset_format()
    assert get_clipboard_text_format() == CLIPBOARD_TEXT_FORMAT_JSON


def test_copy_as_json(qtbot):
    _reset_format()
    model = JsonTreeModel({"x": 1})
    view = QTreeView()
    qtbot.addWidget(view)
    view.setModel(model)
    idx = model.index(0, 0, QModelIndex())
    from PySide6.QtCore import QItemSelectionModel

    view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    view.selectionModel().setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)
    assert copy_selection(view)
    text = QApplication.clipboard().mimeData().text()
    parsed = json.loads(text)
    assert parsed == {"x": 1}


def test_copy_as_yaml(qtbot):
    set_clipboard_text_format(CLIPBOARD_TEXT_FORMAT_YAML)
    try:
        model = JsonTreeModel({"x": 1})
        view = QTreeView()
        qtbot.addWidget(view)
        view.setModel(model)
        idx = model.index(0, 0, QModelIndex())
        from PySide6.QtCore import QItemSelectionModel

        view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        view.selectionModel().setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)
        assert copy_selection(view)
        text = QApplication.clipboard().mimeData().text()
        parsed = yaml.safe_load(text)
        assert parsed == {"x": 1}
    finally:
        _reset_format()


def test_copy_as_yaml_handles_number_affix_in_deep_object(qtbot):
    from units.number_affix import AffixKind, NumberAffix

    set_clipboard_text_format(CLIPBOARD_TEXT_FORMAT_YAML)
    try:
        payload = {
            "nested": {
                "arr": [
                    {
                        "endpoint": NumberAffix(
                            kind=AffixKind.CURRENCY,
                            affix="https://1.2.3.4:",
                            space=False,
                            number=6443,
                        )
                    }
                ]
            }
        }
        model = JsonTreeModel(payload)
        view = QTreeView()
        qtbot.addWidget(view)
        view.setModel(model)
        idx = model.index(0, 0, QModelIndex())
        from PySide6.QtCore import QItemSelectionModel

        view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        view.selectionModel().setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)
        assert copy_selection(view)
        parsed = yaml.safe_load(QApplication.clipboard().mimeData().text())
        assert parsed == {"nested": {"arr": [{"endpoint": "https://1.2.3.4:6443"}]}}
    finally:
        _reset_format()


# ---------------------------------------------------------------------------
# New From Clipboard action
# ---------------------------------------------------------------------------


def test_new_from_clipboard_action_disabled_when_empty(qtbot):
    _set_clipboard_text("")
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileNewFromClipboardAction.isEnabled()
    finally:
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_new_from_clipboard_action_enabled_with_json(qtbot):
    _set_clipboard_text('{"greeting": "hello"}')
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert win.fileNewFromClipboardAction.isEnabled()
    finally:
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_new_from_clipboard_creates_tab_with_json_data(qtbot):
    _set_clipboard_text('{"greeting": "hello"}')
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_count = win.tabWidget.count()
        win.new_from_clipboard()
        assert win.tabWidget.count() == initial_count + 1
        tab = _current_tab(win)
        assert tab.model.root_item.to_json() == {"greeting": "hello"}
    finally:
        for i in range(win.tabWidget.count()):
            w = win.tabWidget.widget(i)
            if isinstance(w, JsonTab):
                w.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_new_from_clipboard_preserves_extreme_floats(qtbot):
    _set_clipboard_text(_EXTREME_FLOATS_JSON)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_count = win.tabWidget.count()
        win.new_from_clipboard()
        assert win.tabWidget.count() == initial_count + 1

        tab = _current_tab(win)
        root = tab.model.root_item.to_json()
        assert isinstance(root["underfloat"], RawNumericValue)
        assert root["underfloat"].raw == "31e-327018450730"
        assert isinstance(root["overfloat"], RawNumericValue)
        assert root["overfloat"].raw == "31e+327018450730"

        under_item = _find_named_item(tab.model.root_item, "underfloat")
        over_item = _find_named_item(tab.model.root_item, "overfloat")
        assert under_item is not None
        assert over_item is not None
        assert under_item.json_type is JsonType.RAW_FLOAT
        assert over_item.json_type is JsonType.RAW_FLOAT
    finally:
        for i in range(win.tabWidget.count()):
            w = win.tabWidget.widget(i)
            if isinstance(w, JsonTab):
                w.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_paste_from_clipboard_preserves_extreme_floats(qtbot):
    _set_clipboard_text(_EXTREME_FLOATS_JSON)

    tab = JsonTab(lambda *_: None, data={"target": []})
    qtbot.addWidget(tab)
    target_view = tab.view.model().index(0, 0, QModelIndex())
    tab.view.setCurrentIndex(target_view)

    assert paste_from_clipboard(tab.view)

    target = tab.model.index(0, 0, QModelIndex())
    pasted = tab.model.get_item(target).to_json()
    assert isinstance(pasted, list)
    assert len(pasted) == 3
    assert isinstance(pasted[0], RawNumericValue)
    assert pasted[0].raw == "31e-327018450730"
    assert pasted[0].reason == REASON_UNDERFLOW
    assert isinstance(pasted[1], RawNumericValue)
    assert pasted[1].raw == "31e+327018450730"
    assert pasted[1].reason == REASON_OVERFLOW
    assert pasted[2] == "$ 31e-327018450730"

    child0 = tab.model.get_item(tab.model.index(0, 0, target))
    child1 = tab.model.get_item(tab.model.index(1, 0, target))
    assert child0.json_type is JsonType.RAW_FLOAT
    assert child1.json_type is JsonType.RAW_FLOAT


def test_new_from_clipboard_creates_tab_with_yaml_data(qtbot):
    _set_clipboard_text("name: Alice\nage: 30\n")
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_count = win.tabWidget.count()
        win.new_from_clipboard()
        assert win.tabWidget.count() == initial_count + 1
        tab = _current_tab(win)
        assert tab.model.root_item.to_json() == {"name": "Alice", "age": 30}
    finally:
        for i in range(win.tabWidget.count()):
            w = win.tabWidget.widget(i)
            if isinstance(w, JsonTab):
                w.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_new_from_clipboard_noop_when_invalid(qtbot):
    _set_clipboard_text("totally invalid text {!!")
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_count = win.tabWidget.count()
        win.new_from_clipboard()
        assert win.tabWidget.count() == initial_count  # no new tab
    finally:
        win.close()
        win.deleteLater()
        QApplication.processEvents()
