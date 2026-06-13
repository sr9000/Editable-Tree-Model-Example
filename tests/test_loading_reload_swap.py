"""Tests for reload build-then-swap behavior (Commit 2.8)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, QTimer
from PySide6.QtWidgets import QApplication

from app.loading.progress import (
    STAGE_APPLYING_RELOAD,
    STAGE_BINDING_UI,
    STAGE_BUILDING_TREE,
    STAGE_COMPLETE,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_READING_PARSING,
    STAGE_VALIDATING_DOCUMENT,
)
from app.main_window import MainWindow
from documents.tab import JsonTab


def _current_tab(win: MainWindow) -> JsonTab:
    tab = win._current_tab()
    assert isinstance(tab, JsonTab)
    return tab


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestReloadSwapStages:
    """Tests for reload stage emission."""

    def test_reload_uses_applying_reload_stage(self, qtbot, tmp_path, monkeypatch):
        """Reload emits 'applying reload' instead of 'binding UI'."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Update the file
            _write_json(doc, {"version": 2})

            stages = []
            win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

            assert win._load_coordinator.reload_file(tab, str(doc))

            # Verify 'applying reload' is used instead of 'binding UI'
            assert STAGE_APPLYING_RELOAD in stages
            assert STAGE_BINDING_UI not in stages
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_emits_all_stages_in_order(self, qtbot, tmp_path, monkeypatch):
        """Reload emits all stages in the correct order."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            _write_json(doc, {"version": 2})

            stages = []
            win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

            assert win._load_coordinator.reload_file(tab, str(doc))

            # Verify order
            assert stages.index(STAGE_READING_PARSING) < stages.index(STAGE_APPLYING_RELOAD)
            assert stages.index(STAGE_APPLYING_RELOAD) < stages.index(STAGE_DISCOVERING_SCHEMA)
            assert stages.index(STAGE_DISCOVERING_SCHEMA) < stages.index(STAGE_VALIDATING_DOCUMENT)
            assert stages.index(STAGE_VALIDATING_DOCUMENT) < stages.index(STAGE_COMPLETE)
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()


class TestReloadSwapDataIntegrity:
    """Tests for reload data integrity."""

    def test_reload_updates_data(self, qtbot, tmp_path, monkeypatch):
        """Reload updates the tab data correctly."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1, "items": [1, 2, 3]})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Verify initial data
            assert tab.model.root_item.to_json() == {"version": 1, "items": [1, 2, 3]}

            # Update the file
            _write_json(doc, {"version": 2, "items": [4, 5, 6, 7]})

            assert win._load_coordinator.reload_file(tab, str(doc))

            # Verify updated data
            assert tab.model.root_item.to_json() == {"version": 2, "items": [4, 5, 6, 7]}
            assert tab.model.estimated_item_count is not None
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_preserves_model_identity_and_replaces_root(self, qtbot, tmp_path, monkeypatch):
        """Reload keeps the same model object but swaps in a new root item."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1, "nested": {"value": 1}})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)
            model_identity = tab.model
            old_root = tab.model.root_item

            _write_json(doc, {"version": 2, "nested": {"value": 2}, "new": [1, 2, 3]})

            assert win._load_coordinator.reload_file(tab, str(doc))

            assert tab.model is model_identity
            assert tab.model.root_item is not old_root
            assert tab.model.root_item.to_json() == {"version": 2, "nested": {"value": 2}, "new": [1, 2, 3]}
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_async_reload_keeps_old_state_until_applying_stage(self, qtbot, tmp_path, monkeypatch):
        """Before `applying reload`, data/dirty/undo remain unchanged while event loop keeps ticking."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            a_name = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
            a_value = a_name.siblingAtColumn(2)
            assert tab.editing.commands.push_edit_value(a_value, 99, label="dirty")
            dirty_snapshot = tab.model.root_item.to_json()
            undo_snapshot = tab.undo_stack.count()
            assert tab.io.dirty

            _write_json(doc, {"version": 2, "items": list(range(200))})

            stages: list[str] = []
            win._load_coordinator.stage_changed.connect(lambda stage: stages.append(stage))

            sampled_data: list[dict] = []
            sampled_undo: list[int] = []
            sampled_dirty: list[bool] = []
            tick_count = [0]

            probe = QTimer(win)

            def _probe() -> None:
                tick_count[0] += 1
                if STAGE_APPLYING_RELOAD in stages:
                    return
                sampled_data.append(tab.model.root_item.to_json())
                sampled_undo.append(tab.undo_stack.count())
                sampled_dirty.append(tab.io.dirty)

            probe.timeout.connect(_probe)
            probe.start(10)

            def slow_parser(_path: str):
                time.sleep(0.2)
                return {"version": 2, "items": list(range(200))}, "json"

            task_id = win._load_coordinator.reload_file_async(tab, str(doc), parser=slow_parser)
            assert task_id is not None

            qtbot.waitUntil(lambda: STAGE_BUILDING_TREE in stages, timeout=2000)
            qtbot.waitUntil(lambda: STAGE_APPLYING_RELOAD in stages, timeout=4000)
            qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=4000)

            assert sampled_data
            assert sampled_undo
            assert sampled_dirty
            assert all(sample == dirty_snapshot for sample in sampled_data)
            assert all(sample == undo_snapshot for sample in sampled_undo)
            assert all(sample is True for sample in sampled_dirty)
            assert tick_count[0] >= 2

            assert tab.model.root_item.to_json() == {"version": 2, "items": list(range(200))}
            assert tab.undo_stack.count() == 0
            assert not tab.io.dirty
        finally:
            probe.stop()
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_clears_undo_stack_on_change(self, qtbot, tmp_path, monkeypatch):
        """Reload clears the undo stack when data changes."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Make an edit to add to undo stack
            a_name = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
            a_value = a_name.siblingAtColumn(2)
            assert tab.editing.commands.push_edit_value(a_value, 99, label="edit")
            assert tab.undo_stack.count() > 0

            # Update the file
            _write_json(doc, {"version": 2})

            assert win._load_coordinator.reload_file(tab, str(doc))

            # Undo stack should be cleared
            assert tab.undo_stack.count() == 0
            assert not tab.io.dirty
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_preserves_clean_state_on_no_change(self, qtbot, tmp_path, monkeypatch):
        """Reload preserves clean state when data doesn't change."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Don't change the file
            assert win._load_coordinator.reload_file(tab, str(doc))

            # Should still be clean
            assert not tab.io.dirty
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()


class TestReloadSwapErrorHandling:
    """Tests for reload error handling."""

    def test_reload_error_preserves_old_data(self, qtbot, tmp_path, monkeypatch):
        """Reload error preserves the old tab data."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Verify initial data
            old_data = tab.model.root_item.to_json()
            assert old_data == {"version": 1}

            # Corrupt the file
            doc.write_text("{invalid json", encoding="utf-8")

            from unittest.mock import patch

            from PySide6.QtWidgets import QMessageBox

            with patch.object(QMessageBox, "critical"):
                assert not win._load_coordinator.reload_file(tab, str(doc))

            # Old data should be preserved
            assert tab.model.root_item.to_json() == old_data
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()
