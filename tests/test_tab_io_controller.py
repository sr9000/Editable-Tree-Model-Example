"""Contract tests for ``documents/tab_io_controller.py``."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from documents.tab import JsonTab
from documents.tab_io_controller import TabIOController


@pytest.fixture(scope="module")
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_tab_exposes_io_controller(_qapp):
    tab = JsonTab(update_actions_callback=lambda: None, data={"a": 1}, file_path="/tmp/x.json")
    try:
        assert isinstance(tab.io, TabIOController)
        assert tab.io.file_path == "/tmp/x.json"
        assert tab.io.file_path == "/tmp/x.json"
        assert tab.io.dirty is False
    finally:
        tab.deleteLater()


def test_dirty_signal_propagates_through_facade(_qapp):
    tab = JsonTab(update_actions_callback=lambda: None, data={"a": 1})
    try:
        events: list[bool] = []
        tab.dirtyChanged.connect(events.append)
        tab._set_dirty(True)
        assert events == [True]
        assert tab.io.dirty is True
        tab._set_dirty(False)
        assert events == [True, False]
    finally:
        tab.deleteLater()


def test_file_path_setter_via_facade(_qapp):
    tab = JsonTab(update_actions_callback=lambda: None, data={"a": 1})
    try:
        tab.io.file_path = "/tmp/new.json"
        assert tab.io.file_path == "/tmp/new.json"
        tab.io.save_format = "json"
        assert tab.io.save_format == "json"
    finally:
        tab.deleteLater()
