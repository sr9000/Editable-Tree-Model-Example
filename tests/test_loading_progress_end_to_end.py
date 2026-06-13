"""End-to-end tests for loading progress widget (Commit 2.7)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.loading.progress import (
    STAGE_APPLYING_RELOAD,
    STAGE_BINDING_UI,
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
