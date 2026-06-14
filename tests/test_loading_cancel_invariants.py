"""Regression invariants for loading cancellation (Plan 3, Commit 3.6)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import state.view_state as view_state
from app.loading.progress import STAGE_BUILDING_TREE
from app.main_window import MainWindow
from app.recent_files import recent_files
from documents.tab import JsonTab
from validation.schema_registry import get_schema_registry


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


def _capture_reload_snapshot(tab: JsonTab) -> dict[str, object]:
    return {
        "model_identity": tab.model,
        "root_identity": tab.model.root_item,
        "data": tab.model.root_item.to_json(),
        "dirty": tab.io.dirty,
        "undo_count": tab.undo_stack.count(),
        "clean_index": tab.undo_stack.cleanIndex(),
        "view": view_state.capture_runtime_state(tab),
        "schema_ref": tab.validation.schema_ref,
        "schema_source": tab.validation.schema_source,
        "issue_count": len(tab.validation.issue_index),
    }


def test_open_cancel_during_build_has_no_recent_schema_or_validation_side_effects(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "open-cancel.json"
    _write_json(doc, {"seed": True})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_tabs = win.tabWidget.count()
        initial_recent = list(recent_files(win))
        initial_schema_entries = len(get_schema_registry().all_entries())
        initial_schema_pool = len(win._schema_tab_pool._tabs_by_source)

        hook_done = [False]

        def parser(_path: str):
            return {"items": [{"id": i, "value": i} for i in range(12000)]}, "json"

        def _on_stage(stage: str) -> None:
            if stage != STAGE_BUILDING_TREE or hook_done[0]:
                return
            hook_done[0] = True
            QTimer.singleShot(0, win._load_coordinator.cancel_current)

        win._load_coordinator.stage_changed.connect(_on_stage)

        with patch.object(QMessageBox, "critical") as mock_critical:
            task_id = win._load_coordinator.open_file_async(str(doc), parser=parser)
            assert task_id is not None
            assert not win._load_coordinator._run_blocking(task_id)

            qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=4000)
            assert win._load_coordinator._current_task_id is None
            assert win.tabWidget.count() == initial_tabs
            assert list(recent_files(win)) == initial_recent
            assert len(get_schema_registry().all_entries()) == initial_schema_entries
            assert len(win._schema_tab_pool._tabs_by_source) == initial_schema_pool
            assert all(
                not isinstance(win.tabWidget.widget(i), JsonTab)
                or win.tabWidget.widget(i).io.file_path != str(doc.resolve())
                for i in range(win.tabWidget.count())
            )
            assert "Open cancelled" in win.statusBar.currentMessage()
            mock_critical.assert_not_called()
    finally:
        _cleanup(win)


def test_reload_cancel_preserves_dirty_undo_validation_and_view_state(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "reload-cancel.json"
    _write_json(doc, {"a": 1, "items": [{"id": i, "value": i} for i in range(600)]})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        root_index = tab.model.index(0, 0, QModelIndex())
        a_name = tab.model.index(0, 0, root_index)
        a_value = a_name.siblingAtColumn(2)
        assert tab.editing.commands.push_edit_value(a_value, 99, label="dirty")

        items_index = tab.model.index(1, 0, root_index)
        if items_index.isValid():
            tab.view.expand(items_index)
        tab.view.selectionModel().setCurrentIndex(
            a_value,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )
        QApplication.processEvents()

        before = _capture_reload_snapshot(tab)
        _write_json(doc, {"a": 2, "items": [{"id": i, "value": -i} for i in range(12000)]})

        hook_done = [False]

        def parser(_path: str):
            return {"a": 2, "items": [{"id": i, "value": -i} for i in range(12000)]}, "json"

        def _on_stage(stage: str) -> None:
            if stage != STAGE_BUILDING_TREE or hook_done[0]:
                return
            hook_done[0] = True
            QTimer.singleShot(0, win._load_coordinator.cancel_current)

        win._load_coordinator.stage_changed.connect(_on_stage)

        with patch.object(QMessageBox, "critical") as mock_critical:
            task_id = win._load_coordinator.reload_file_async(tab, str(doc), parser=parser)
            assert task_id is not None
            assert not win._load_coordinator._run_blocking(task_id)

            qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=4000)
            after = _capture_reload_snapshot(tab)
            assert after == before
            assert "Reload cancelled" in win.statusBar.currentMessage()
            mock_critical.assert_not_called()
    finally:
        _cleanup(win)


def test_late_parse_success_after_cancel_is_discarded(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "late-success.json"
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

        qtbot.wait(350)
        assert win.tabWidget.count() == initial_tabs
        assert list(recent_files(win)) == initial_recent
        assert task_id not in win._load_coordinator._tasks
    finally:
        _cleanup(win)


def test_late_parse_failure_after_cancel_is_silent(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "late-failure.json"
    _write_json(doc, {"version": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        with patch.object(QMessageBox, "critical") as mock_critical:

            def slow_failing_parser(_path: str):
                time.sleep(0.2)
                raise ValueError("late parse failure")

            task_id = win._load_coordinator.open_file_async(str(doc), parser=slow_failing_parser)
            assert task_id is not None

            QTimer.singleShot(10, win._load_coordinator.cancel_current)
            assert not win._load_coordinator._run_blocking(task_id)

            qtbot.wait(350)
            mock_critical.assert_not_called()
            assert task_id not in win._load_coordinator._tasks
    finally:
        _cleanup(win)


def test_cancelled_task_releases_single_task_guard_for_next_open(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_json(first, {"id": 1})
    _write_json(second, {"id": 2})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:

        def slow_parser(_path: str):
            time.sleep(0.2)
            return {"id": 1}, "json"

        first_task_id = win._load_coordinator.open_file_async(str(first), parser=slow_parser)
        assert first_task_id is not None

        QTimer.singleShot(10, win._load_coordinator.cancel_current)
        assert not win._load_coordinator._run_blocking(first_task_id)
        assert win._load_coordinator._current_task_id is None

        second_task_id = win._load_coordinator.open_file_async(
            str(second),
            parser=lambda _path: ({"id": 2, "ok": True}, "json"),
        )
        assert second_task_id is not None
        assert win._load_coordinator._run_blocking(second_task_id)

        tab = _current_tab(win)
        assert tab.model.root_item.to_json() == {"id": 2, "ok": True}
    finally:
        _cleanup(win)
