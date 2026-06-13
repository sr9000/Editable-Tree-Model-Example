"""Tests for schema/validation progress stages (Commit 2.6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.loading.coordinator import LoadCoordinator
from app.loading.progress import (
    STAGE_COMPLETE,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_VALIDATING_DOCUMENT,
    NullProgressReporter,
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


class TestCoordinatorStageSignals:
    """Tests for coordinator stage signal emission."""

    def test_coordinator_emits_stage_changed_signal(self, qtbot, tmp_path, monkeypatch):
        """Coordinator emits stage_changed signal when stages change."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            stages = []
            win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

            # Open a file to get a tab
            doc = tmp_path / "data.json"
            _write_json(doc, {"key": "value"})
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Run schema discovery and validation
            win._load_coordinator.run_schema_discovery_and_validation(tab)

            # Verify stages were emitted
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

    def test_coordinator_stages_in_correct_order(self, qtbot, tmp_path, monkeypatch):
        """Coordinator emits stages in the correct order."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            stages = []
            win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

            doc = tmp_path / "data.json"
            _write_json(doc, {"key": "value"})
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            win._load_coordinator.run_schema_discovery_and_validation(tab)

            # Verify order
            assert stages.index(STAGE_DISCOVERING_SCHEMA) < stages.index(STAGE_VALIDATING_DOCUMENT)
            assert stages.index(STAGE_VALIDATING_DOCUMENT) < stages.index(STAGE_COMPLETE)
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()


class TestCoordinatorProgressReporter:
    """Tests for coordinator progress reporter integration."""

    def test_coordinator_notifies_reporter(self, qtbot, tmp_path, monkeypatch):
        """Coordinator notifies the progress reporter of stages."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            reported_stages = []

            class TrackingReporter:
                def stage(self, name: str) -> None:
                    reported_stages.append(name)

                def tick(self, done: int, total: int) -> None:
                    pass

            reporter = TrackingReporter()
            win._load_coordinator.set_reporter(reporter)

            doc = tmp_path / "data.json"
            _write_json(doc, {"key": "value"})
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            win._load_coordinator.run_schema_discovery_and_validation(tab)

            # Verify reporter received stages
            assert STAGE_DISCOVERING_SCHEMA in reported_stages
            assert STAGE_VALIDATING_DOCUMENT in reported_stages
            assert STAGE_COMPLETE in reported_stages
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_coordinator_works_without_reporter(self, qtbot, tmp_path, monkeypatch):
        """Coordinator works correctly without a reporter set."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            # Don't set a reporter
            assert win._load_coordinator._reporter is None

            doc = tmp_path / "data.json"
            _write_json(doc, {"key": "value"})
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Should not raise
            win._load_coordinator.run_schema_discovery_and_validation(tab)
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()
