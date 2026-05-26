"""Tests for Ctrl+W (close tab) and Ctrl+Shift+T (reopen closed tab)."""
from __future__ import annotations

import json

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from documents.tab import JsonTab


def _current_tab(win: MainWindow) -> JsonTab | None:
    return win._current_tab()


def _tab_count(win: MainWindow) -> int:
    return win.tabWidget.count()


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        w = win.tabWidget.widget(i)
        if isinstance(w, JsonTab):
            w.undo_stack.setClean()
    win.close()
    win.deleteLater()
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# close_current_tab (Ctrl+W)
# ---------------------------------------------------------------------------


def test_close_tab_action_disabled_with_no_tabs(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileCloseTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_close_tab_action_enabled_with_tab(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        win.update_actions()
        assert win.fileCloseTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_close_current_tab_removes_tab(qtbot, monkeypatch):
    # Patch confirm to auto-accept
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        assert _tab_count(win) == 1
        win.close_current_tab()
        assert _tab_count(win) == 0
    finally:
        _cleanup(win)


def test_close_current_tab_noop_when_no_tab(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.close_current_tab()  # Should not raise
        assert _tab_count(win) == 0
    finally:
        _cleanup(win)


def test_close_cancels_if_user_cancels(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"x": 1})
        assert tab is not None
        # Make dirty
        idx = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        tab.push_edit_value(idx.siblingAtColumn(2), 99, label="dirty")
        assert tab.is_dirty

        win.close_current_tab()
        assert _tab_count(win) == 1  # Not closed
    finally:
        _cleanup(win)


# ---------------------------------------------------------------------------
# Reopen closed tab (Ctrl+Shift+T)
# ---------------------------------------------------------------------------


def test_reopen_action_disabled_initially(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileReopenTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_reopen_action_enabled_after_close(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        win.close_current_tab()
        win.update_actions()
        assert win.fileReopenTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_reopen_restores_clean_tab_data(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"msg": "hello"})
        assert _tab_count(win) == 1
        win.close_current_tab()
        assert _tab_count(win) == 0

        win.reopen_closed_tab()
        assert _tab_count(win) == 1
        tab = _current_tab(win)
        assert tab is not None
        assert tab.model.root_item.to_json() == {"msg": "hello"}
    finally:
        _cleanup(win)


def test_reopen_multiple_tabs_lifo_order(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"first": 1})
        win._add_tab(data={"second": 2})
        assert _tab_count(win) == 2

        # Close second (current) → stack: [first, second]... actually LIFO so second is on top
        win.close_current_tab()  # closes second
        win.close_current_tab()  # closes first
        assert _tab_count(win) == 0

        # Reopen: should get 'first' (last closed = top of LIFO)
        win.reopen_closed_tab()
        tab = _current_tab(win)
        assert tab is not None
        data = tab.model.root_item.to_json()
        assert data == {"first": 1}

        # Reopen again: should get 'second'
        win.reopen_closed_tab()
        tab = _current_tab(win)
        assert tab is not None
        data = tab.model.root_item.to_json()
        assert data == {"second": 2}
    finally:
        _cleanup(win)


def test_reopen_after_discard_does_not_resurrect_dirty_data(qtbot, monkeypatch, tmp_path):
    """When user discards dirty changes on close, reopen should reload from file."""
    doc = tmp_path / "data.json"
    doc.write_text(json.dumps({"original": True}), encoding="utf-8")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        # Make tab dirty
        first_row = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        tab.push_edit_value(first_row.siblingAtColumn(2), "dirty_value", label="dirty")
        assert tab.is_dirty

        win.close_current_tab()  # User chose Discard
        assert _tab_count(win) == 0

        win.reopen_closed_tab()
        # Should reload from disk — original clean data
        tab = _current_tab(win)
        assert tab is not None
        data = tab.model.root_item.to_json()
        assert data == {"original": True}  # NOT the dirty value
    finally:
        _cleanup(win)
