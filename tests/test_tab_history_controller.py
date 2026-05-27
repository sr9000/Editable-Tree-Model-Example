"""Contract tests for ``documents/tab_history.py``."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QApplication

from documents.tab import JsonTab
from documents.tab_history import TabHistoryController


@pytest.fixture(scope="module")
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_tab_exposes_history_controller(_qapp):
    tab = JsonTab(update_actions_callback=lambda: None, data={"a": 1})
    try:
        assert isinstance(tab.data_store.history, TabHistoryController)
        assert isinstance(tab.data_store.history.undo_stack, QUndoStack)
        # ``tab.data_store.undo_stack`` façade is the same instance.
        assert tab.data_store.undo_stack is tab.data_store.history.undo_stack
    finally:
        tab.deleteLater()


def test_view_state_registration(_qapp):
    tab = JsonTab(update_actions_callback=lambda: None, data={"a": 1})
    try:
        tab.data_store.history.register_view_state(7, {"selection": []})
        assert tab.data_store.history.has_view_state(7)
        assert tab.data_store.history.view_state_for(7) == {"selection": []}
        # Deprecated alias still works.
        assert tab.data_store._move_view_state_by_cmd_id is tab.data_store.history._move_view_state_by_cmd_id
        assert 7 in tab.data_store._move_view_state_by_cmd_id
    finally:
        tab.deleteLater()


def test_last_undo_index_property(_qapp):
    tab = JsonTab(update_actions_callback=lambda: None, data={"a": 1})
    try:
        assert tab.data_store._last_undo_index == tab.data_store.history.last_undo_index
        tab.data_store._last_undo_index = 42
        assert tab.data_store.history.last_undo_index == 42
    finally:
        tab.deleteLater()
