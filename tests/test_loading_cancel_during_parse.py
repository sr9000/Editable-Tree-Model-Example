"""Tests for cancellation during worker parse stage (Plan 3, Commit 3.3)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QModelIndex, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app.main_window import MainWindow
from app.recent_files import recent_files
from documents.tab import JsonTab


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _current_tab(win: MainWindow) -> JsonTab:
    tab = win._current_tab()
    assert isinstance(tab, JsonTab)
    return tab


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()
    QApplication.processEvents()


def test_cancel_open_during_parse_drops_late_success(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"version": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_tabs = win.tabWidget.count()
        initial_recent = list(recent_files(win))

        def slow_parser(_path: str):
            time.sleep(0.2)
            return {"version": 2, "late": True}, "json"

        task_id = win._load_coordinator.open_file_async(str(doc), parser=slow_parser)
        assert task_id is not None

        QTimer.singleShot(10, win._load_coordinator.cancel_current)
        assert not win._load_coordinator._run_blocking(task_id)

        assert win._load_coordinator._current_task_id is None
        assert win.tabWidget.count() == initial_tabs
        assert list(recent_files(win)) == initial_recent
        assert "Open cancelled" in win.statusBar.currentMessage()

        qtbot.wait(350)
        assert win.tabWidget.count() == initial_tabs
        assert list(recent_files(win)) == initial_recent
        assert task_id not in win._load_coordinator._tasks
    finally:
        _cleanup(win)


def test_cancel_reload_during_parse_preserves_pre_reload_state(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        a_name = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        a_value = a_name.siblingAtColumn(2)
        assert tab.editing.commands.push_edit_value(a_value, 99, label="dirty")

        pre_data = tab.model.root_item.to_json()
        pre_dirty = tab.io.dirty
        pre_undo_count = tab.undo_stack.count()

        _write_json(doc, {"a": 2, "b": 3})

        def slow_parser(_path: str):
            time.sleep(0.2)
            return {"a": 2, "b": 3}, "json"

        task_id = win._load_coordinator.reload_file_async(tab, str(doc), parser=slow_parser)
        assert task_id is not None

        QTimer.singleShot(10, win._load_coordinator.cancel_current)
        assert not win._load_coordinator._run_blocking(task_id)

        assert win._load_coordinator._current_task_id is None
        assert tab.model.root_item.to_json() == pre_data
        assert tab.io.dirty == pre_dirty
        assert tab.undo_stack.count() == pre_undo_count
        assert "Reload cancelled" in win.statusBar.currentMessage()

        qtbot.wait(350)
        assert tab.model.root_item.to_json() == pre_data
        assert tab.io.dirty == pre_dirty
        assert tab.undo_stack.count() == pre_undo_count
        assert task_id not in win._load_coordinator._tasks
    finally:
        _cleanup(win)


def test_late_parse_failure_after_cancel_shows_no_error_dialog(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"version": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:

        def slow_failing_parser(_path: str):
            time.sleep(0.2)
            raise ValueError("late parse failure")

        with patch.object(QMessageBox, "critical") as mock_critical:
            task_id = win._load_coordinator.open_file_async(str(doc), parser=slow_failing_parser)
            assert task_id is not None
            QTimer.singleShot(10, win._load_coordinator.cancel_current)

            assert not win._load_coordinator._run_blocking(task_id)
            qtbot.wait(350)

            mock_critical.assert_not_called()
            assert task_id not in win._load_coordinator._tasks
    finally:
        _cleanup(win)
