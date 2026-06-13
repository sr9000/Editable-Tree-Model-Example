"""Tests for atomic cancel-safe reload behavior (Plan 3, Commit 3.5)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QItemSelectionModel, QModelIndex, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import state.view_state as view_state
from app.loading.progress import STAGE_BUILDING_TREE
from app.main_window import MainWindow
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


def _make_dirty_and_snapshot(tab: JsonTab) -> dict[str, object]:
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

    v_scroll = tab.view.verticalScrollBar()
    if v_scroll.maximum() > 0:
        v_scroll.setValue(min(20, v_scroll.maximum()))

    h_scroll = tab.view.horizontalScrollBar()
    if h_scroll.maximum() > 0:
        h_scroll.setValue(min(10, h_scroll.maximum()))

    QApplication.processEvents()
    return _capture_reload_snapshot(tab)


@pytest.mark.parametrize("checkpoint", ["parse", "build", "before_swap"])
def test_cancelled_reload_preserves_pre_reload_snapshot(qtbot, tmp_path, monkeypatch, checkpoint):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1, "items": [{"id": i, "value": i} for i in range(300)]})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)
        before = _make_dirty_and_snapshot(tab)

        _write_json(doc, {"a": 2, "items": [{"id": i, "value": -i} for i in range(1200)]})

        hooked = [False]

        if checkpoint == "parse":

            def parser(_path: str):
                time.sleep(0.2)
                return {"a": 2, "items": [{"id": i, "value": -i} for i in range(1200)]}, "json"

            schedule_cancel = lambda: QTimer.singleShot(10, win._load_coordinator.cancel_current)

        elif checkpoint == "build":

            def parser(_path: str):
                return {"a": 2, "items": [{"id": i, "value": -i} for i in range(12000)]}, "json"

            def _on_stage(stage: str) -> None:
                if stage != STAGE_BUILDING_TREE or hooked[0]:
                    return
                hooked[0] = True
                QTimer.singleShot(0, win._load_coordinator.cancel_current)

            win._load_coordinator.stage_changed.connect(_on_stage)
            schedule_cancel = lambda: None

        else:

            def parser(_path: str):
                return {"a": 2, "items": [{"id": i, "value": -i} for i in range(1200)]}, "json"

            original_apply = win._load_coordinator._apply_reload

            def _cancel_before_swap(task, model):
                task.token.cancel()
                return original_apply(task, model)

            monkeypatch.setattr(win._load_coordinator, "_apply_reload", _cancel_before_swap)
            schedule_cancel = lambda: None

        with patch.object(QMessageBox, "critical") as mock_critical:
            task_id = win._load_coordinator.reload_file_async(tab, str(doc), parser=parser)
            assert task_id is not None
            schedule_cancel()

            assert not win._load_coordinator._run_blocking(task_id)
            qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=4000)

            after = _capture_reload_snapshot(tab)
            assert after["model_identity"] is before["model_identity"]
            assert after["root_identity"] is before["root_identity"]
            assert after["data"] == before["data"]
            assert after["dirty"] == before["dirty"]
            assert after["undo_count"] == before["undo_count"]
            assert after["clean_index"] == before["clean_index"]
            assert after["schema_ref"] == before["schema_ref"]
            assert after["schema_source"] == before["schema_source"]
            assert after["issue_count"] == before["issue_count"]
            assert after["view"] == before["view"]
            assert "Reload cancelled" in win.statusBar.currentMessage()
            mock_critical.assert_not_called()
    finally:
        _cleanup(win)


def test_reload_without_cancellation_preserves_existing_reload_behavior(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1, "items": [1, 2, 3]})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        model_identity = tab.model
        old_root = tab.model.root_item

        _write_json(doc, {"a": 2, "items": [4, 5, 6, 7]})

        assert win._load_coordinator.reload_file(tab, str(doc))
        assert tab.model is model_identity
        assert tab.model.root_item is not old_root
        assert tab.model.root_item.to_json() == {"a": 2, "items": [4, 5, 6, 7]}
        assert not tab.io.dirty
    finally:
        _cleanup(win)


def test_reload_does_not_recheck_token_after_swap_begins(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"version": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        _write_json(doc, {"version": 2})

        original_replace = tab.model.replace_root_item

        def _replace_and_cancel(root_item, *, estimated_item_count=None):
            active_task = next(iter(win._load_coordinator._tasks.values()))
            active_task.token.cancel()
            return original_replace(root_item, estimated_item_count=estimated_item_count)

        monkeypatch.setattr(tab.model, "replace_root_item", _replace_and_cancel)

        assert win._load_coordinator.reload_file(tab, str(doc))
        assert tab.model.root_item.to_json() == {"version": 2}
        assert "Reloaded" in win.statusBar.currentMessage()
    finally:
        _cleanup(win)
