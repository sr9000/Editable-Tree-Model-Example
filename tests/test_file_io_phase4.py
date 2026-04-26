import pytest
import simplejson
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication, QMessageBox

from enums import JsonType
from file_io import (
    SAVE_FORMAT_JSONL,
    SAVE_FORMAT_YAML_MULTI,
    dump_text,
    load_file_with_format,
    save_file,
)
from json_tab import JsonTab
from ui import MainWindow


def _close_window_cleanly(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        tab = win.tabWidget.widget(i)
        if hasattr(tab, "undo_stack"):
            tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dirty(tab) -> None:
    assert tab.push_insert_rows(
        [
            {
                "parent_path": (),
                "row": 0,
                "value": 1,
                "name": "a",
            }
        ],
        label="insert",
    )


def test_setup_model_loads_json_file(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    path = tmp_path / "in.json"
    path.write_text('{"name": "demo", "n": 1.25}\n', encoding="utf-8")

    win = MainWindow(str(path))
    try:
        assert win.tabWidget.count() == 1
        tab = win.tabWidget.widget(0)
        assert tab.file_path == str(path.resolve())
        assert tab.model.root_item.to_json()["name"] == "demo"
    finally:
        _close_window_cleanly(win)


def test_setup_model_loads_json_array_root(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    path = tmp_path / "in.json"
    path.write_text('[1, 2, 3]\n', encoding="utf-8")

    win = MainWindow(str(path))
    try:
        tab = win.tabWidget.widget(0)
        assert tab.model.root_item.to_json() == [1, 2, 3]
    finally:
        _close_window_cleanly(win)


def test_setup_model_loads_yaml_multi_doc_as_root_array(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    path = tmp_path / "in.yaml"
    path.write_text("a: 1\n---\nb: 2\n", encoding="utf-8")

    win = MainWindow(str(path))
    try:
        tab = win.tabWidget.widget(0)
        assert tab.model.root_item.to_json() == [{"a": 1}, {"b": 2}]
    finally:
        _close_window_cleanly(win)


def test_dirty_flips_on_edit_and_clears_on_save(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    win = MainWindow("")
    try:
        win.create_new_file()
        tab = win.tabWidget.currentWidget()
        assert not tab.is_dirty

        _make_dirty(tab)
        assert tab.is_dirty

        out = tmp_path / "saved.json"
        assert tab.save_as(str(out))
        assert not tab.is_dirty

        parsed = simplejson.loads(out.read_text(encoding="utf-8"))
        assert parsed == {"a": 1}
    finally:
        _close_window_cleanly(win)


def test_close_dirty_tab_cancel_keeps_tab_open(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    win = MainWindow("")
    try:
        win.create_new_file()
        tab = win.tabWidget.currentWidget()
        _make_dirty(tab)

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)
        win.close_tab(0)
        assert win.tabWidget.count() == 1
        assert win.tabWidget.widget(0) is tab
    finally:
        _close_window_cleanly(win)


def test_load_file_with_format_json_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")

    data, fmt = load_file_with_format(str(path))
    assert fmt == SAVE_FORMAT_JSONL
    assert data == [{"a": 1}, {"b": 2}]


def test_load_file_with_format_yaml_multi_document(tmp_path):
    path = tmp_path / "events.yaml"
    path.write_text("a: 1\n---\nb: 2\n", encoding="utf-8")

    data, fmt = load_file_with_format(str(path))
    assert fmt == SAVE_FORMAT_YAML_MULTI
    assert data == [{"a": 1}, {"b": 2}]


def test_dump_text_yaml_multi_and_jsonl(tmp_path):
    payload = [{"a": 1}, {"b": 2}]

    yaml_text = dump_text(str(tmp_path / "out.yaml"), payload, save_format=SAVE_FORMAT_YAML_MULTI)
    assert "---" in yaml_text

    jsonl_text = dump_text(str(tmp_path / "out.jsonl"), payload, save_format=SAVE_FORMAT_JSONL)
    assert jsonl_text.count("\n") == 2
    assert jsonl_text.splitlines()[0] == '{"a": 1}'


def test_json_tab_shows_special_root_and_allows_root_type_change(qapp):
    tab = JsonTab(lambda *_args, **_kwargs: None, data={"a": 1}, show_root=True)
    try:
        root = tab.model.index(0, 0, QModelIndex())
        assert root.isValid()
        assert tab.model.data(root) == "<root>"

        root_type = tab.model.index(0, 1, QModelIndex())
        assert tab.commit_set_data(root_type, JsonType.ARRAY)
        assert tab.model.root_item.to_json() == []

        assert tab.commit_set_data(root_type, JsonType.OBJECT)
        assert tab.model.root_item.to_json() == {}
    finally:
        tab.deleteLater()


def test_sort_keys_on_root_object(qapp):
    tab = JsonTab(lambda *_args, **_kwargs: None, data={"z": 1, "a": 2}, show_root=True)
    try:
        root = tab.model.index(0, 0, QModelIndex())
        assert tab.push_sort_keys(root)
        assert list(tab.model.root_item.to_json().keys()) == ["a", "z"]
    finally:
        tab.deleteLater()


def test_save_file_yaml_multi_roundtrip(tmp_path):
    payload = [{"a": 1}, {"b": 2}]
    path = tmp_path / "multi.yaml"

    save_file(str(path), payload, save_format=SAVE_FORMAT_YAML_MULTI)
    loaded, fmt = load_file_with_format(str(path))
    assert fmt == SAVE_FORMAT_YAML_MULTI
    assert loaded == payload


def test_json_tab_save_jsonl_mode(tmp_path, qapp):
    tab = JsonTab(lambda *_args, **_kwargs: None, data=[{"a": 1}, {"b": 2}], show_root=True)
    try:
        out = tmp_path / "events.jsonl"
        tab.file_path = str(out)
        tab.save_format = SAVE_FORMAT_JSONL
        assert tab.save()
        assert out.read_text(encoding="utf-8") == '{"a": 1}\n{"b": 2}\n'
    finally:
        tab.deleteLater()
