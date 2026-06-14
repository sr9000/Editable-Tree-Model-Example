"""Tests for LoadCoordinator scaffold (Commit 2.1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.loading.coordinator import LoadCoordinator
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


class TestLoadCoordinatorOpen:
    """Tests for LoadCoordinator.open_file()."""

    def test_open_file_creates_tab(self, qtbot, tmp_path, monkeypatch):
        """Opening a file creates a tab with the correct data."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"key": "value"})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._load_coordinator.open_file(str(doc))
            assert win.tabWidget.count() == 1
            tab = _current_tab(win)
            assert tab.io.file_path == str(doc.resolve())
            assert tab.model.root_item.to_json() == {"key": "value"}
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_open_file_shows_error_on_invalid_json(self, qtbot, tmp_path, monkeypatch):
        """Opening an invalid JSON file shows an error and returns False."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "bad.json"
        doc.write_text("{invalid json", encoding="utf-8")

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            with patch.object(QMessageBox, "critical") as mock_critical:
                assert not win._load_coordinator.open_file(str(doc))
                mock_critical.assert_called_once()
                # QMessageBox.critical(parent, title, text) - check positional args
                call_args = mock_critical.call_args
                assert call_args[0][1] == "Open failed"
        finally:
            win.close()
            win.deleteLater()

    def test_open_path_routes_through_coordinator(self, qtbot, tmp_path, monkeypatch):
        """_open_path() routes through the LoadCoordinator."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"routed": True})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            with patch.object(win._load_coordinator, "open_file", wraps=win._load_coordinator.open_file) as mock_open:
                assert win._open_path(str(doc))
                mock_open.assert_called_once_with(str(doc))
        finally:
            for i in range(win.tabWidget.count()):
                maybe_tab = win.tabWidget.widget(i)
                if isinstance(maybe_tab, JsonTab):
                    maybe_tab.undo_stack.setClean()
            win.close()
            win.deleteLater()


class TestLoadCoordinatorReload:
    """Tests for LoadCoordinator.reload_file()."""

    def test_reload_file_updates_data(self, qtbot, tmp_path, monkeypatch):
        """Reloading a file updates the tab data."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"version": 1})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)
            assert tab.model.root_item.to_json() == {"version": 1}

            # Update the file on disk
            _write_json(doc, {"version": 2})

            # Reload
            assert win._load_coordinator.reload_file(tab, str(doc))
            assert tab.model.root_item.to_json() == {"version": 2}
            assert not tab.io.dirty
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_file_shows_error_on_invalid_json(self, qtbot, tmp_path, monkeypatch):
        """Reloading an invalid JSON file shows an error and returns False."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"valid": True})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            # Corrupt the file on disk
            doc.write_text("{invalid json", encoding="utf-8")

            with patch.object(QMessageBox, "critical") as mock_critical:
                assert not win._load_coordinator.reload_file(tab, str(doc))
                mock_critical.assert_called_once()
                # QMessageBox.critical(parent, title, text) - check positional args
                call_args = mock_critical.call_args
                assert call_args[0][1] == "Reload failed"
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()

    def test_reload_tab_from_path_routes_through_coordinator(self, qtbot, tmp_path, monkeypatch):
        """_reload_tab_from_path() routes through the LoadCoordinator."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        doc = tmp_path / "data.json"
        _write_json(doc, {"routed": True})

        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)
        try:
            assert win._open_path(str(doc))
            tab = _current_tab(win)

            with patch.object(
                win._load_coordinator, "reload_file", wraps=win._load_coordinator.reload_file
            ) as mock_reload:
                assert win._reload_tab_from_path(tab, str(doc))
                mock_reload.assert_called_once_with(tab, str(doc))
        finally:
            tab.undo_stack.setClean()
            win.close()
            win.deleteLater()
