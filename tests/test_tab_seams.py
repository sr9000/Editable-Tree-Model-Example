"""Contract tests for the Phase-0 façades on ``JsonTab``."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from documents.controllers.history import TabHistoryController
from documents.seams.mutation_gateway import DocumentMutationGateway
from documents.tab import JsonTab


@pytest.fixture(scope="module")
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tab(_qapp):
    t = JsonTab(update_actions_callback=lambda: None, data={"a": 1})
    yield t
    t.deleteLater()


def test_tab_exposes_mutations_gateway(tab):
    assert isinstance(tab.mutations, DocumentMutationGateway)


def test_tab_exposes_history_facade(tab):
    assert isinstance(tab.editing.history, TabHistoryController)
    assert tab.editing.history.undo_stack is tab.undo_stack


def test_history_view_state_registration(tab):
    tab.editing.history.register_view_state(42, {"expanded_rel": []})
    assert tab.editing.history.view_state_for(42) == {"expanded_rel": []}
    assert tab.editing.history.view_state_for(99) is None
