"""End-to-end tests for loading progress widget (Commit 2.7)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.loading.progress import (
    STAGE_APPLYING_RELOAD,
    STAGE_BINDING_UI,
    STAGE_COMPLETE,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_READING_PARSING,
    STAGE_VALIDATING_DOCUMENT,
)
from app.loading.progress_dialog import LoadingProgressDialog
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


class TestLoadingProgressEndToEnd:
    """End-to-end tests for loading progress widget."""

    def test_fast_open_shows_no_widget(self, qtbot, tmp_path, monkeypatch):
        """A fast open operation does not show the progress widget."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"key": "value"})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            # Open the file
            assert win._open_path(str(doc))

            # The progress dialog should not have been shown
            # (it's created but never made visible for fast operations)
            if win._load_coordinator._progress_dialog is not None:
                assert not win._load_coordinator._progress_dialog.was_shown
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_open_emits_all_stages(self, qtbot, tmp_path, monkeypatch):
        """Opening a file emits all expected stages."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"key": "value"})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            stages = []
            win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

            assert win._open_path(str(doc))

            # Verify all stages were emitted
            assert STAGE_READING_PARSING in stages
            assert STAGE_BINDING_UI in stages
            assert STAGE_DISCOVERING_SCHEMA in stages
            assert STAGE_VALIDATING_DOCUMENT in stages
            assert STAGE_COMPLETE in stages
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_emits_all_stages(self, qtbot, tmp_path, monkeypatch):
        """Reloading a file emits all expected stages."""
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

            # Verify all stages were emitted (reload uses APPLYING_RELOAD instead of BINDING_UI)
            assert STAGE_READING_PARSING in stages
            assert STAGE_APPLYING_RELOAD in stages
            assert STAGE_DISCOVERING_SCHEMA in stages
            assert STAGE_VALIDATING_DOCUMENT in stages
            assert STAGE_COMPLETE in stages
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_open_error_hides_widget(self, qtbot, tmp_path, monkeypatch):
        """An error during open hides the progress widget."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "bad.json"
        doc.write_text("{invalid json", encoding="utf-8")

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            with patch.object(QMessageBox, "critical"):
                assert not win._open_path(str(doc))

            # The progress dialog should not be visible after error
            if win._load_coordinator._progress_dialog is not None:
                assert not win._load_coordinator._progress_dialog.isVisible()
        finally:
            win.close()
            win.deleteLater()

    def test_reload_error_hides_widget(self, qtbot, tmp_path, monkeypatch):
        """An error during reload hides the progress widget."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"valid": True})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Corrupt the file
            doc.write_text("{invalid json", encoding="utf-8")

            with patch.object(QMessageBox, "critical"):
                assert not win._load_coordinator.reload_file(tab, str(doc))

            # The progress dialog should not be visible after error
            if win._load_coordinator._progress_dialog is not None:
                assert not win._load_coordinator._progress_dialog.isVisible()
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_async_open_returns_immediately_and_shows_progress(self, qtbot, tmp_path, monkeypatch):
        """A slow async open keeps the event loop alive and shows progress."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"key": "value"})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        progress = LoadingProgressDialog(win, delay_ms=50, detail_refresh_ms=20)
        qtbot.addWidget(progress)
        win._load_coordinator._progress_dialog = progress

        timer_count = [0]

        def on_timer():
            timer_count[0] += 1

        timer = QTimer(win)
        timer.timeout.connect(on_timer)
        timer.start(20)

        payload = {
            "items": [
                {
                    "id": i,
                    "value": f"item_{i}",
                }
                for i in range(300)
            ]
        }

        def slow_parser(_path: str):
            time.sleep(0.2)
            return payload, "json"

        try:
            task_id = win._load_coordinator.open_file_async(str(doc), parser=slow_parser)
            assert task_id is not None
            assert win.tabWidget.count() == 0

            qtbot.waitUntil(lambda: progress.was_shown, timeout=1000)
            assert timer_count[0] >= 2

            qtbot.waitUntil(lambda: progress._detail_label.text() != "", timeout=2000)
            assert "Processed" in progress._detail_label.text()
            assert "/" in progress._detail_label.text()

            qtbot.waitUntil(lambda: win.tabWidget.count() == 1, timeout=2000)
            assert not progress.isVisible()
            tab = _current_tab(win)
            loaded = tab.model.root_item.to_json()
            assert isinstance(loaded, dict)
            assert "items" in loaded
            assert len(loaded["items"]) == 300
        finally:
            timer.stop()
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_open_file_dialog_starts_async_open(self, qtbot, tmp_path, monkeypatch):
        """The native open dialog returns before loading starts."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"key": "value"})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(doc), "")):
                with patch.object(win._load_coordinator, "open_file_async") as mock_open_async:
                    win.open_file_dialog()
                    mock_open_async.assert_called_once_with(str(doc))
        finally:
            win.close()
            win.deleteLater()
