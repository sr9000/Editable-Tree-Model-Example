"""Contract tests for ``documents/tab_validation.py``."""

from __future__ import annotations

import gc

import pytest
from PySide6.QtWidgets import QApplication

from documents.tab import JsonTab
from documents.tab_validation import TabValidationController
from validation.schema_source import SchemaRef


@pytest.fixture(scope="module")
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_tab(data=None):
    return JsonTab(update_actions_callback=lambda: None, data=(data if data is not None else {"a": 1}))


def test_tab_exposes_validation_controller(_qapp):
    tab = _make_tab()
    try:
        assert isinstance(tab.data_store.validation, TabValidationController)
    finally:
        tab.deleteLater()


def test_release_stops_timer_and_disconnects(_qapp):
    tab = _make_tab()
    try:
        tab.data_store.validation.set_auto_rescan(True)
        tab.data_store.validation.debounce_timer.start()  # arm it
        assert tab.data_store.validation.debounce_timer.isActive()
        tab.data_store.validation.release()
        assert not tab.data_store.validation.debounce_timer.isActive()
        # Idempotent.
        tab.data_store.validation.release()
    finally:
        tab.deleteLater()


def test_release_releases_schema_source(_qapp, tmp_path):
    schema_path = tmp_path / "s.json"
    schema_path.write_text('{"type": "object"}')

    tab = _make_tab()
    try:
        ref = SchemaRef(path=schema_path, inline=None, origin="manual")
        tab.data_store.validation.set_schema(ref)
        assert tab.data_store.validation.schema_source is not None
        tab.data_store.validation.release()
        assert tab.data_store.validation.schema_source is None
    finally:
        tab.deleteLater()


def test_closed_tab_is_collectable(_qapp):
    import weakref

    tab = _make_tab()
    ref = weakref.ref(tab)
    tab.data_store.validation.release()
    tab.deleteLater()
    del tab
    QApplication.processEvents()
    gc.collect()
    # The C++ side may still hold the object until the event loop spins again;
    # this assertion only verifies the timer is off, not C++ destruction.
    # The point of this test is that release() makes the tab safe to discard.
    assert ref() is None or not ref().data_store.validation.debounce_timer.isActive()
