from __future__ import annotations

import json

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from documents.tab import JsonTab


def _current_tab(win: MainWindow) -> JsonTab:
    tab = win._current_tab()
    assert isinstance(tab, JsonTab)
    return tab


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_reload_action_enabled_state(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileReloadAction.isEnabled()

        tab = win._add_tab(data={"a": 1}, file_path=None)
        assert tab is not None
        win.update_actions()
        assert not win.fileReloadAction.isEnabled()

        tab.file_path = "/tmp/reloadable.json"
        win._refresh_tab_presentation(tab)
        win.update_actions()
        assert win.fileReloadAction.isEnabled()
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_reload_from_disk_saves_then_reloads(qtbot, tmp_path, monkeypatch):
    """Dirty tab: Ok saves in-memory state to disk first, then reloads from that file.

    The old 'Discard' path (reload disk content, losing local edits) is no longer
    offered.  Reload now always saves dirty changes before re-reading the file.
    """
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        a_name = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        a_value = a_name.siblingAtColumn(2)
        assert tab.push_edit_value(a_value, 99, label="dirty")
        assert tab.is_dirty

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

        win.reload_from_disk()

        # After save-first reload: in-memory value 99 was saved, then reloaded.
        assert tab.model.root_item.to_json() == {"a": 99}
        assert not tab.is_dirty
        # Confirm the file on disk was actually written.
        assert json.loads(doc.read_text()) == {"a": 99}
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_reload_from_disk_cancel_keeps_current_state(qtbot, tmp_path, monkeypatch):
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        a_name = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        a_value = a_name.siblingAtColumn(2)
        assert tab.push_edit_value(a_value, 99, label="dirty")
        assert tab.is_dirty

        _write_json(doc, {"a": 2})
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)

        win.reload_from_disk()

        assert tab.model.root_item.to_json() == {"a": 99}
        assert tab.is_dirty
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()
