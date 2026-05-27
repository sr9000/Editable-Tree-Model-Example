from __future__ import annotations

import json

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

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

        tab.data_store.file_path = "/tmp/reloadable.json"
        win._refresh_tab_presentation(tab)
        win.update_actions()
        assert win.fileReloadAction.isEnabled()
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.data_store.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_reload_from_disk_discard_reloads_disk_state(qtbot, tmp_path, monkeypatch):
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        a_name = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0, QModelIndex()))
        a_value = a_name.siblingAtColumn(2)
        assert tab.push_edit_value(a_value, 99, label="dirty")
        assert tab.data_store.is_dirty

        def _choose_discard(box):
            box: QMessageBox

            for btn in box.buttons():
                btn: QPushButton
                if QMessageBox.ButtonRole.DestructiveRole is box.buttonRole(btn):
                    return btn
            return None

        monkeypatch.setattr(QMessageBox, "exec", lambda box: _choose_discard(box) and box.clickedButton())
        monkeypatch.setattr(QMessageBox, "clickedButton", _choose_discard)

        _write_json(doc, {"a": 2})

        win.reload_from_disk()

        assert tab.data_store.model.root_item.to_json() == {"a": 2}
        assert not tab.data_store.is_dirty
        assert json.loads(doc.read_text()) == {"a": 2}
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.data_store.undo_stack.setClean()
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

        a_name = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0, QModelIndex()))
        a_value = a_name.siblingAtColumn(2)
        assert tab.push_edit_value(a_value, 99, label="dirty")
        assert tab.data_store.is_dirty

        _write_json(doc, {"a": 2})

        def _choose_cancel(box):
            for btn in box.buttons():
                if btn.text().replace("&", "") == "Cancel":
                    return btn
            return None

        monkeypatch.setattr(QMessageBox, "exec", lambda box: _choose_cancel(box) and box.clickedButton())
        monkeypatch.setattr(QMessageBox, "clickedButton", _choose_cancel)

        win.reload_from_disk()

        assert tab.data_store.model.root_item.to_json() == {"a": 99}
        assert tab.data_store.is_dirty
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.data_store.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_reload_from_disk_overwrite_saves_then_reloads(qtbot, tmp_path, monkeypatch):
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        a_name = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0, QModelIndex()))
        a_value = a_name.siblingAtColumn(2)
        assert tab.push_edit_value(a_value, 99, label="dirty")
        assert tab.data_store.is_dirty

        def _choose_overwrite(box):
            box: QMessageBox
            for btn in box.buttons():
                btn: QPushButton
                if QMessageBox.ButtonRole.AcceptRole is box.buttonRole(btn):
                    return btn
            return None

        monkeypatch.setattr(QMessageBox, "exec", lambda box: _choose_overwrite(box) and box.clickedButton())
        monkeypatch.setattr(QMessageBox, "clickedButton", _choose_overwrite)

        _write_json(doc, {"a": 2})
        win.reload_from_disk()

        assert tab.data_store.model.root_item.to_json() == {"a": 99}
        assert not tab.data_store.is_dirty
        assert json.loads(doc.read_text()) == {"a": 99}
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.data_store.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()
